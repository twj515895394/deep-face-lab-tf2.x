import os
import sys
import gc
import traceback
import queue
import threading
import time
import numpy as np
import itertools
from pathlib import Path
from core import pathex
from core import imagelib
import cv2
import models
from core.interact import interact as io
from samplelib.sampling.loss_stats import LossWindowTracker
from mainscripts.trainer_save_control import TrainerSaveController


def _error_richness_score(msg):
    """Higher when structured save context (reason/iter) is present."""
    if not isinstance(msg, dict):
        return -1
    score = 0
    if msg.get("reason") not in (None, "", "unknown"):
        score += 2
    if msg.get("iter") is not None:
        score += 2
    if msg.get("error"):
        score += 1
    if msg.get("traceback"):
        score += 1
    if msg.get("error_type"):
        score += 1
    return score


def prefer_richer_error(existing, incoming):
    """
    Keep first rich save error; do not let a generic outer error wipe reason/iter.

    T19-R3-01: Controller emits {reason, iter, ...}; trainerThread outer except may
    emit a second generic error. Prefer the richer payload, merging missing fields.
    """
    if existing is None:
        return incoming if isinstance(incoming, dict) else None
    if not isinstance(incoming, dict):
        return existing
    ex_score = _error_richness_score(existing)
    in_score = _error_richness_score(incoming)
    if in_score > ex_score:
        base = dict(incoming)
        for key in ("reason", "iter", "error", "error_type", "traceback"):
            if base.get(key) in (None, "", "unknown") and existing.get(key) not in (None, ""):
                base[key] = existing[key]
        return base
    # Keep existing; fill blanks from incoming only.
    base = dict(existing)
    for key in ("reason", "iter", "error", "error_type", "traceback"):
        if base.get(key) in (None, "", "unknown") and incoming.get(key) not in (None, ""):
            base[key] = incoming[key]
    return base


class TrainerClientState:
    """
    Main-thread view of trainerThread messages.

    Fatal save/train errors must not be treated as a normal close.
    """

    def __init__(self):
        self.fatal_error = None  # type: dict | None
        self.closed = False
        self.last_show = None  # type: dict | None

    def on_message(self, msg):
        """
        Apply one c2s message.

        Returns:
          'continue'  — keep polling
          'show'      — preview payload available on last_show
          'exit_ok'   — normal close
          'exit_error'— fatal error then close (or fatal alone)
        """
        if not isinstance(msg, dict):
            return "continue"
        op = msg.get("op", "")
        if op == "error":
            self.fatal_error = prefer_richer_error(self.fatal_error, msg)
            return "continue"
        if op == "close":
            self.closed = True
            return "exit_error" if self.fatal_error is not None else "exit_ok"
        if op == "show":
            self.last_show = msg
            return "show"
        return "continue"

    def raise_if_fatal(self):
        if self.fatal_error is None:
            return
        err = self.fatal_error
        reason = err.get("reason") or "unknown"
        error_type = err.get("error_type") or "Error"
        error = err.get("error") or "trainer fatal error"
        iter_num = err.get("iter")
        tb = err.get("traceback") or ""
        parts = [
            f"Trainer fatal error ({error_type})",
            f"reason={reason}",
        ]
        if iter_num is not None:
            parts.append(f"iter={iter_num}")
        parts.append(str(error))
        message = ": ".join(parts[:1]) + " [" + ", ".join(parts[1:-1]) + "]: " + parts[-1]
        if tb:
            message = message + "\n" + tb
        raise RuntimeError(message)


def trainerThread (s2c, c2s, e,
                    model_class_name = None,
                    saved_models_path = None,
                    training_data_src_path = None,
                    training_data_dst_path = None,
                    pretraining_data_path = None,
                    pretrained_model_path = None,
                    no_preview=False,
                    force_model_name=None,
                    force_gpu_idxs=None,
                    cpu_only=None,
                    silent_start=False,
                    execute_programs = None,
                    debug=False,
                    options_json=None,
                    **kwargs):
    while True:
        try:
            start_time = time.time()

            save_interval_min = 25

            # CUDA Graph warmup: run a few iterations before timing
            cuda_graph_warmup_iters = 3

            if not training_data_src_path.exists():
                training_data_src_path.mkdir(exist_ok=True, parents=True)

            if not training_data_dst_path.exists():
                training_data_dst_path.mkdir(exist_ok=True, parents=True)

            if not saved_models_path.exists():
                saved_models_path.mkdir(exist_ok=True, parents=True)
                            
            model = models.import_model(model_class_name)(
                        is_training=True,
                        saved_models_path=saved_models_path,
                        training_data_src_path=training_data_src_path,
                        training_data_dst_path=training_data_dst_path,
                        pretraining_data_path=pretraining_data_path,
                        pretrained_model_path=pretrained_model_path,
                        no_preview=no_preview,
                        force_model_name=force_model_name,
                        force_gpu_idxs=force_gpu_idxs,
                        cpu_only=cpu_only,
                        silent_start=silent_start,
                        options_json=options_json,
                        debug=debug)

            try:
                save_interval_min = max(1, int(model.options.get('save_interval_min', 25)))
            except Exception:
                save_interval_min = 25
            io.log_info(f"Auto-save interval: {save_interval_min} minutes.")

            # Session-local window buffer: empty on resume so old history is not mixed in.
            loss_window = LossWindowTracker()
            ctrl = TrainerSaveController(
                model=model,
                loss_window=loss_window,
                c2s=c2s,
                debug=debug,
                warmup_iters=cuda_graph_warmup_iters,
                log_info_fn=io.log_info,
            )
            is_reached_goal = ctrl.is_reached_goal

            loss_string = ""

            def model_backup():
                if not debug and not ctrl.is_reached_goal:
                    model.create_backup()

            def send_preview():
                if not debug:
                    previews = model.get_previews()
                    c2s.put ( {'op':'show', 'previews': previews, 'iter':model.get_iter(), 'loss_history': model.get_loss_history().copy() } )
                else:
                    previews = [( 'debug, press update for new', model.debug_one_iter())]
                    c2s.put ( {'op':'show', 'previews': previews} )
                e.set() #Set the GUI Thread as Ready

            if model.get_target_iter() != 0:
                if ctrl.is_reached_goal:
                    io.log_info('Model already trained to target iteration. You can use preview.')
                else:
                    io.log_info('Starting. Target iteration: %d. Press "Enter" to stop training and save model.' % ( model.get_target_iter()  ) )
            else:
                io.log_info('Starting. Press "Enter" to stop training and save model.')

            last_save_time = time.time()

            timed_execute_programs = [ [x[0], x[1], time.time() ] for x in execute_programs ]

            def _on_preview_cmd():
                if ctrl.is_reached_goal:
                    model.pass_one_iter()
                send_preview()

            for i in itertools.count(0,1):
                # High-priority control commands before any train group.
                if ctrl.process_commands(
                    s2c,
                    on_manual_save_success=send_preview,
                    on_preview=_on_preview_cmd,
                    on_backup=model_backup,
                ):
                    break

                if not debug:
                    cur_time = time.time()

                    for x in timed_execute_programs:
                        prog_time, prog, last_time = x
                        exec_prog = False
                        if prog_time > 0 and (cur_time - start_time) >= prog_time:
                            x[0] = 0
                            exec_prog = True
                        elif prog_time < 0 and (cur_time - last_time)  >= -prog_time:
                            x[2] = cur_time
                            exec_prog = True

                        if exec_prog:
                            try:
                                exec(prog)
                            except Exception as e:
                                print("Unable to execute program: %s" % (prog) )

                    if not ctrl.is_reached_goal:

                        if model.get_iter() == 0:
                            io.log_info("")
                            io.log_info("Trying to do the first iteration. If an error occurs, reduce the model parameters.")
                            io.log_info("")
                            
                            if sys.platform[0:3] == 'win':
                                io.log_info("!!!")
                                io.log_info("Windows 10 users IMPORTANT notice. You should set this setting in order to work correctly.")
                                io.log_info("https://i.imgur.com/B7cmDCB.jpg")
                                io.log_info("!!!")

                        # Warmup + timed train; stop early on target / queued close.
                        timed = ctrl.run_train_group(s2c)
                        is_reached_goal = ctrl.is_reached_goal

                        if timed is not None:
                            iter, iter_time = timed
                            loss_history = model.get_loss_history()
                            time_str = time.strftime("[%H:%M:%S]")
                            if iter_time >= 10:
                                loss_string = "{0}[#{1:06d}][{2:.5s}s]".format ( time_str, iter, '{:0.4f}'.format(iter_time) )
                            else:
                                loss_string = "{0}[#{1:06d}][{2:04d}ms]".format ( time_str, iter, int(iter_time*1000) )

                            if len(loss_history) > 0:
                                last_loss = loss_history[-1]
                                if not hasattr(last_loss, '__iter__') or isinstance(last_loss, (np.number, float, int, str, bytes)):
                                    loss_values = [last_loss]
                                else:
                                    loss_values = last_loss
                                for loss_value in loss_values:
                                    loss_string += "[%.4f]" % (loss_value)

                            if io.is_colab():
                                io.log_info ('\r' + loss_string, end='')
                            else:
                                io.log_info (loss_string, end='\r')

                        if ctrl.should_stop:
                            break

                need_save = False
                # Multiple elapsed intervals collapse to one save (single window consume).
                while time.time() - last_save_time >= save_interval_min*60:
                    last_save_time += save_interval_min*60
                    need_save = True
                
                if not ctrl.is_reached_goal and need_save:
                    if ctrl.model_save(reason="scheduled"):
                        send_preview()

                if i==0:
                    if ctrl.is_reached_goal:
                        model.pass_one_iter()
                    send_preview()

                if debug:
                    time.sleep(0.005)

                # Drain any commands that arrived during the train group.
                if ctrl.process_commands(
                    s2c,
                    on_manual_save_success=send_preview,
                    on_preview=_on_preview_cmd,
                    on_backup=model_backup,
                ):
                    break

            model.finalize()

            del model
            gc.collect()

            from core.leras import nn as leras_nn
            leras_nn.compact_gpu_memory()

        except Exception as e:
            print ('Error: %s' % (str(e)))
            traceback.print_exc()
            # If Controller already put a rich {reason, iter, ...} error, do not
            # overwrite it with a generic outer exception payload (T19-R3-01).
            already_reported = False
            try:
                if 'ctrl' in locals() and getattr(ctrl, 'last_error', None) is not None:
                    already_reported = True
            except Exception:
                already_reported = False
            if not already_reported:
                try:
                    payload = {
                        'op': 'error',
                        'error': str(e),
                        'error_type': type(e).__name__,
                        'traceback': traceback.format_exc(),
                    }
                    try:
                        if 'ctrl' in locals() and ctrl is not None:
                            if getattr(ctrl, 'save_reasons', None):
                                # Best-effort context when Controller did not emit.
                                payload.setdefault('reason', 'trainer_exception')
                            payload.setdefault('iter', int(model.get_iter()) if 'model' in locals() else None)
                    except Exception:
                        pass
                    c2s.put(payload)
                except Exception:
                    pass
            try:
                if 'model' in locals():
                    model.finalize()
                    del model
                gc.collect()
                from core.leras import nn as leras_nn
                leras_nn.compact_gpu_memory()
            except:
                pass
            # Unblock main() if failure happened before the first preview signal.
            try:
                e.set()
            except Exception:
                pass
        break
    c2s.put ( {'op':'close'} )



def main(**kwargs):
    io.log_info ("Running trainer.\r\n")

    no_preview = kwargs.get('no_preview', False)

    s2c = queue.Queue()
    c2s = queue.Queue()

    e = threading.Event()
    thread = threading.Thread(target=trainerThread, args=(s2c, c2s, e), kwargs=kwargs )
    thread.start()

    e.wait() #Wait for inital load to occur.

    client_state = TrainerClientState()

    if no_preview:
        while True:
            if not c2s.empty():
                input = c2s.get()
                action = client_state.on_message(input)
                if action == 'exit_ok' or action == 'exit_error':
                    break
                if action == 'continue' and client_state.fatal_error is not None:
                    # Log immediately; still wait for trainerThread close so join is clean.
                    err = client_state.fatal_error
                    io.log_err(
                        f"[Trainer] fatal: {err.get('error_type')}: {err.get('error')} "
                        f"(reason={err.get('reason')}, iter={err.get('iter')})"
                    )
            try:
                io.process_messages(0.1)
            except KeyboardInterrupt:
                s2c.put ( {'op': 'close'} )
        try:
            thread.join(timeout=120)
        except Exception:
            pass
        client_state.raise_if_fatal()
    else:
        wnd_name = "Training preview"
        io.named_window(wnd_name)
        io.capture_keys(wnd_name)

        previews = None
        loss_history = None
        selected_preview = 0
        update_preview = False
        is_showing = False
        is_waiting_preview = False
        show_last_history_iters_count = 0
        iter = 0
        while True:
            if not c2s.empty():
                input = c2s.get()
                action = client_state.on_message(input)
                if action == 'exit_ok' or action == 'exit_error':
                    break
                if action == 'continue' and client_state.fatal_error is not None:
                    err = client_state.fatal_error
                    io.log_err(
                        f"[Trainer] fatal: {err.get('error_type')}: {err.get('error')} "
                        f"(reason={err.get('reason')}, iter={err.get('iter')})"
                    )
                    # Keep looping until close so UI can still exit cleanly.
                    continue
                if action != 'show':
                    continue
                is_waiting_preview = False
                loss_history = input['loss_history'] if 'loss_history' in input.keys() else None
                previews = input['previews'] if 'previews' in input.keys() else None
                iter = input['iter'] if 'iter' in input.keys() else 0
                if previews is not None:
                    max_w = 0
                    max_h = 0
                    for (preview_name, preview_rgb) in previews:
                        (h, w, c) = preview_rgb.shape
                        max_h = max (max_h, h)
                        max_w = max (max_w, w)

                    max_size = 800
                    if max_h > max_size:
                        max_w = int( max_w / (max_h / max_size) )
                        max_h = max_size

                    #make all previews size equal
                    for preview in previews[:]:
                        (preview_name, preview_rgb) = preview
                        (h, w, c) = preview_rgb.shape
                        if h != max_h or w != max_w:
                            previews.remove(preview)
                            previews.append ( (preview_name, cv2.resize(preview_rgb, (max_w, max_h))) )
                    selected_preview = selected_preview % len(previews)
                    update_preview = True

            if update_preview:
                update_preview = False

                selected_preview_name = previews[selected_preview][0]
                selected_preview_rgb = previews[selected_preview][1]
                (h,w,c) = selected_preview_rgb.shape

                # HEAD
                head_lines = [
                    '[s]:save [b]:backup [enter]:exit',
                    '[p]:update [space]:next preview [l]:change history range',
                    'Preview: "%s" [%d/%d]' % (selected_preview_name,selected_preview+1, len(previews) )
                    ]
                head_line_height = 15
                head_height = len(head_lines) * head_line_height
                head = np.ones ( (head_height,w,c) ) * 0.1

                for i in range(0, len(head_lines)):
                    t = i*head_line_height
                    b = (i+1)*head_line_height
                    head[t:b, 0:w] += imagelib.get_text_image (  (head_line_height,w,c) , head_lines[i], color=[0.8]*c )

                final = head

                if loss_history is not None:
                    if show_last_history_iters_count == 0:
                        loss_history_to_show = loss_history
                    else:
                        loss_history_to_show = loss_history[-show_last_history_iters_count:]

                    lh_img = models.ModelBase.get_loss_history_preview(loss_history_to_show, iter, w, c)
                    final = np.concatenate ( [final, lh_img], axis=0 )

                final = np.concatenate ( [final, selected_preview_rgb], axis=0 )
                final = np.clip(final, 0, 1)

                io.show_image( wnd_name, (final*255).astype(np.uint8) )
                is_showing = True

            key_events = io.get_key_events(wnd_name)
            key, chr_key, ctrl_pressed, alt_pressed, shift_pressed = key_events[-1] if len(key_events) > 0 else (0,0,False,False,False)

            if key == ord('\n') or key == ord('\r'):
                s2c.put ( {'op': 'close'} )
            elif key == ord('s'):
                s2c.put ( {'op': 'save'} )
            elif key == ord('b'):
                s2c.put ( {'op': 'backup'} )
            elif key == ord('p'):
                if not is_waiting_preview:
                    is_waiting_preview = True
                    s2c.put ( {'op': 'preview'} )
            elif key == ord('l'):
                if show_last_history_iters_count == 0:
                    show_last_history_iters_count = 5000
                elif show_last_history_iters_count == 5000:
                    show_last_history_iters_count = 10000
                elif show_last_history_iters_count == 10000:
                    show_last_history_iters_count = 50000
                elif show_last_history_iters_count == 50000:
                    show_last_history_iters_count = 100000
                elif show_last_history_iters_count == 100000:
                    show_last_history_iters_count = 0
                update_preview = True
            elif key == ord(' '):
                selected_preview = (selected_preview + 1) % len(previews)
                update_preview = True

            try:
                io.process_messages(0.1)
            except KeyboardInterrupt:
                s2c.put ( {'op': 'close'} )

        io.destroy_all_windows()
        try:
            thread.join(timeout=120)
        except Exception:
            pass
        client_state.raise_if_fatal()
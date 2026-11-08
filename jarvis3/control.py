"""Explicit assistant exit: priority control message and inference cancellation."""
import queue,re,threading
CANCEL_INFERENCE=threading.Event()
EXIT_PHRASES={'shut down','shutdown','quit','exit','goodbye','go to sleep','power off','turn yourself off','close yourself','shut yourself down'}
def assistant_exit(text):
    value=re.sub(r'[^a-z ]',' ',str(text).lower());value=' '.join(value.split())
    value=re.sub(r'^(?:(?:can|could|would|will) you(?: please)?|please)\s+','',value)
    value=re.sub(r'^(?:(?:hey|hi|ok|okay) )?jarvis\s+','',value)
    value=re.sub(r' please$','',value)
    return value in EXIT_PHRASES
class ControlQueue(queue.Queue):
    def urgent(self,item):
        with self.not_full:
            self.queue.appendleft(item);self.unfinished_tasks+=1;self.not_empty.notify()

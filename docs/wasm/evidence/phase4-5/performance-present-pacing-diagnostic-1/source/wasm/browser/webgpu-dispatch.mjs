// Bound each browser task so command encoding can overlap CPU recording while
// rendering/input/RAF get opportunities between ordered command packets.
function postPresentation(run) {
  let done=false,frame=null,timer=null;
  const cancel=()=>{
    if(frame!==null)cancelAnimationFrame(frame);
    if(timer!==null)clearTimeout(timer);
    document.removeEventListener('visibilitychange',visibility);
  };
  const finish=()=>{if(done)return;done=true;cancel();run();};
  const visibility=()=>{if(document.hidden)finish();};
  // Hidden windows do not receive RAF. Keep resource fences and shutdown able
  // to drain; foreground presentation always uses the actual display callback.
  if(document.hidden)timer=setTimeout(finish,0);
  else {document.addEventListener('visibilitychange',visibility);frame=requestAnimationFrame(finish);}
  return ()=>{done=true;cancel();};
}

export class CommandDispatcher {
  constructor({budgetMs=4,now=()=>performance.now(),post=null,
    postFrame=typeof requestAnimationFrame==='function' && typeof document!=='undefined'?postPresentation:null}={}) {
    this.budgetMs=budgetMs;this.now=now;this.post=post;this.queue=[];
    this.postFrame=postFrame;this.cancelFrame=null;
    this.scheduled=false;this.disposed=false;this.current=null;this.channel=null;
  }
  enqueue(run,ack=()=>{},onError=error=>{throw error;},frameBoundary=false) {
    const job={run,ack,onError,done:false,frameBoundary};
    if(this.disposed){this.complete(job,false);return;}
    this.queue.push(job);this.schedule();
  }
  complete(job,success){if(!job.done){job.done=true;job.ack(success);}}
  schedule() {
    if(this.scheduled||this.disposed||!this.queue.length)return;
    this.scheduled=true;
    if(this.post){this.post(()=>this.drain());return;}
    if(!this.channel){this.channel=new MessageChannel();this.channel.port1.onmessage=()=>this.drain();}
    this.channel.port2.postMessage(0);
  }
  drain(frameReady=false) {
    if(this.disposed)return;
    const deadline=this.now()+this.budgetMs;
    do {
      if(this.queue[0].frameBoundary && this.postFrame && !frameReady){
        this.cancelFrame=this.postFrame(()=>{this.cancelFrame=null;this.drain(true);});
        return;
      }
      const job=this.queue.shift();this.current=job;
      frameReady=false;
      try {job.run();this.complete(job,!this.disposed);}
      catch(error){this.complete(job,false);this.dispose();job.onError(error);return;}
      finally {this.current=null;}
    } while(!this.disposed&&this.queue.length&&this.now()<deadline);
    this.scheduled=false;this.schedule();
  }
  dispose() {
    if(this.disposed)return;this.disposed=true;
    this.cancelFrame?.();this.cancelFrame=null;
    // An active command still borrows C++ payload memory. Its acknowledgement
    // must wait until run() returns, including when run() requests disposal.
    for(const job of this.queue)this.complete(job,false);
    this.queue=[];this.channel?.port1.close();this.channel?.port2.close();this.channel=null;
  }
}

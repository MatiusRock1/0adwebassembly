// Bound each browser task so command encoding can overlap CPU recording while
// rendering/input/RAF get opportunities between ordered command packets.
export class CommandDispatcher {
  constructor({budgetMs=4,now=()=>performance.now(),post=null}={}) {
    this.budgetMs=budgetMs;this.now=now;this.post=post;this.queue=[];
    this.scheduled=false;this.disposed=false;this.current=null;this.channel=null;
  }
  enqueue(run,ack=()=>{},onError=error=>{throw error;}) {
    const job={run,ack,onError,done:false};
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
  drain() {
    if(this.disposed)return;
    const deadline=this.now()+this.budgetMs;
    do {
      const job=this.queue.shift();this.current=job;
      try {job.run();this.complete(job,!this.disposed);}
      catch(error){this.complete(job,false);this.dispose();job.onError(error);return;}
      finally {this.current=null;}
    } while(!this.disposed&&this.queue.length&&this.now()<deadline);
    this.scheduled=false;this.schedule();
  }
  dispose() {
    if(this.disposed)return;this.disposed=true;
    // An active command still borrows C++ payload memory. Its acknowledgement
    // must wait until run() returns, including when run() requests disposal.
    for(const job of this.queue)this.complete(job,false);
    this.queue=[];this.channel?.port1.close();this.channel?.port2.close();this.channel=null;
  }
}

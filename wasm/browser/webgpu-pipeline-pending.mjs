// An internal continuation marker, not a draw failure. Only the render worker
// enables asynchronous compilation and resumes the same command after it.
export class PipelinePending extends Error {
  constructor(promise){super('Pipeline compilation pending');this.promise=promise;}
}

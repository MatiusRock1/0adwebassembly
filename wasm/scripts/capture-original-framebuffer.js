// Functional capture only. Read the original persistent render target after
// its frame observer fires; preserve all GL state and never edit artwork.
async function captureOriginalFramebuffer()
{
  const module = window.application;
  const frames = module.applicationFrames;
  return await new Promise((resolve, reject) => {
    const original = frames.push;
    const hadOwnPush = Object.hasOwn(frames, 'push');
    let pending = true;
    const restore = () => { if (hadOwnPush) frames.push = original; else delete frames.push; };
    const timer = setTimeout(() => {
      if (pending) { pending = false; restore(); reject(new Error('Original frame completion timeout')); }
    }, 20000);
    frames.push = function(...samples) {
      const result = original.apply(this, samples);
      if (!pending) return result;
      pending = false;
      clearTimeout(timer);
      restore();
      readFrame().then(resolve, reject);
      return result;
    };
  });

  async function readFrame() {
    const canvas = document.getElementById('canvas');
    const frame = module.applicationState.frame;
    const width = canvas.width, height = canvas.height;
    const rgba = new Uint8ClampedArray(width * height * 4);
    const backend = window.rendererDiagnostics?.backend || 'webgl';
    if (backend === 'webgpu') {
      const renderer = window.webgpuBackend, device = renderer.device;
      const pitch = Math.ceil(width * 4 / 256) * 256;
      const buffer = device.createBuffer({size:pitch * height, usage:GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ});
      try {
        const encoder = device.createCommandEncoder();
        encoder.copyTextureToBuffer({texture:renderer.presentationTexture}, {buffer,bytesPerRow:pitch}, [width,height,1]);
        device.queue.submit([encoder.finish()]);
        await buffer.mapAsync(GPUMapMode.READ);
        const bytes = new Uint8Array(buffer.getMappedRange());
        const bgra = renderer.session.diagnostics.format.startsWith('bgra');
        for (let y=0;y<height;y++) for(let x=0;x<width;x++) {
          const source=y*pitch+x*4, target=(y*width+x)*4;
          rgba[target]=bytes[source+(bgra?2:0)];rgba[target+1]=bytes[source+1];rgba[target+2]=bytes[source+(bgra?0:2)];rgba[target+3]=255;
        }
        buffer.unmap();
      } finally { buffer.destroy(); }
    } else {
      const gl = canvas.getContext('webgl2'), context = canvas.GLctxObject;
      if (!context?.defaultFbo || !gl) throw new Error('Original GL framebuffer unavailable');
      const previous = gl.getParameter(gl.READ_FRAMEBUFFER_BINDING);
      const packBuffer = gl.getParameter(gl.PIXEL_PACK_BUFFER_BINDING);
      const parameters = [gl.PACK_ALIGNMENT,gl.PACK_ROW_LENGTH,gl.PACK_SKIP_ROWS,gl.PACK_SKIP_PIXELS];
      const pack = parameters.map(parameter=>gl.getParameter(parameter));
      const pixels = new Uint8Array(rgba.length);
      try {
        gl.bindFramebuffer(gl.READ_FRAMEBUFFER,context.defaultFbo);
        if (gl.checkFramebufferStatus(gl.READ_FRAMEBUFFER)!==gl.FRAMEBUFFER_COMPLETE) throw new Error('Original GL framebuffer incomplete');
        gl.bindBuffer(gl.PIXEL_PACK_BUFFER,null);
        parameters.forEach((parameter,index)=>gl.pixelStorei(parameter,index===0?1:0));
        gl.readPixels(0,0,width,height,gl.RGBA,gl.UNSIGNED_BYTE,pixels);
        const error=gl.getError();if(error!==gl.NO_ERROR)throw new Error('Original RGBA readback GL error '+error);
      } finally {
        parameters.forEach((parameter,index)=>gl.pixelStorei(parameter,pack[index]));
        gl.bindBuffer(gl.PIXEL_PACK_BUFFER,packBuffer);
        gl.bindFramebuffer(gl.READ_FRAMEBUFFER,previous);
      }
      for(let y=0;y<height;y++) {
        rgba.set(pixels.subarray((height-1-y)*width*4,(height-y)*width*4),y*width*4);
        for(let x=0;x<width;x++)rgba[(y*width+x)*4+3]=255;
      }
    }
    // The original presentation surfaces are opaque. PNG encoding keeps the
    // framebuffer RGB bytes; row orientation/BGRA are transport conversions.
    const output = new OffscreenCanvas(width,height);
    output.getContext('2d').putImageData(new ImageData(rgba,width,height),0,0);
    const bytes = new Uint8Array(await (await output.convertToBlob({type:'image/png'})).arrayBuffer());
    const parts=[];for(let i=0;i<bytes.length;i+=32768)parts.push(String.fromCharCode(...bytes.subarray(i,i+32768)));
    return {png:btoa(parts.join('')),width,height,backend,frame};
  }
}

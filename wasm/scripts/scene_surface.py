"""Inspect actual backing attachments, independently of canvas/engine dimensions."""
def inspect_surface(page):
    return page.evaluate("""async () => {
        const canvas = document.querySelector('#canvas');
        const gpu = window.webgpuBackend;
        if (window.rendererDiagnostics?.backend === 'webgpu') {
            if(gpu?.remote){
                const surface=await gpu.rpc('surface');
                const display=document.querySelector('#render-canvas');
                const rect=display.getBoundingClientRect(),style=getComputedStyle(display);
                if(rect.width<=0 || rect.height<=0 || style.visibility==='hidden' || Number(style.opacity)===0)
                    throw Error('Render worker display surface is hidden');
                return {...surface,backend:'webgpu',owner:'render-worker',canvas:[canvas.width,canvas.height],
                    fullscreen:document.fullscreenElement===(document.querySelector('#game-surface') || canvas),
                    innerSize:[innerWidth,innerHeight],dpr:devicePixelRatio,focused:document.hasFocus(),hidden:document.hidden};
            }
            if (!gpu?.presentationTexture || !gpu?.depthTexture) throw Error('WebGPU attachments unavailable');
            return {backend:'webgpu',canvas:[canvas.width,canvas.height],
                    drawingBuffer:[gpu.width,gpu.height],
                    proxiedDepthAttachment:[gpu.depthTexture.width,gpu.depthTexture.height],
                    colorAttachment:[gpu.presentationTexture.width,gpu.presentationTexture.height],
                    viewport:gpu.viewportRect,fullscreen:document.fullscreenElement===(document.querySelector('#game-surface') || canvas),
                    innerSize:[innerWidth,innerHeight],dpr:devicePixelRatio,
                    focused:document.hasFocus(),hidden:document.hidden};
        }
        const context = canvas.GLctxObject;
        const gl = canvas.getContext('webgl2');
        if (!context?.defaultDepthTarget || !gl) throw Error('Proxied framebuffer unavailable');
        const previous = gl.getParameter(gl.RENDERBUFFER_BINDING);
        gl.bindRenderbuffer(gl.RENDERBUFFER, context.defaultDepthTarget);
        const depth = [gl.getRenderbufferParameter(gl.RENDERBUFFER, gl.RENDERBUFFER_WIDTH),
                       gl.getRenderbufferParameter(gl.RENDERBUFFER, gl.RENDERBUFFER_HEIGHT)];
        gl.bindRenderbuffer(gl.RENDERBUFFER, previous);
        return {canvas: [canvas.width, canvas.height],
                drawingBuffer: [gl.drawingBufferWidth, gl.drawingBufferHeight],
                proxiedDepthAttachment: depth,
                viewport: Array.from(gl.getParameter(gl.VIEWPORT)),
                fullscreen: document.fullscreenElement === (document.querySelector('#game-surface') || canvas),
                innerSize: [innerWidth, innerHeight], dpr: devicePixelRatio,
                focused:document.hasFocus(),hidden:document.hidden};
    }""")


def assert_surface(page, width, height):
    surface = inspect_surface(page)
    for name in ['canvas', 'drawingBuffer', 'proxiedDepthAttachment']:
        assert surface[name] == [width, height], f'{name} resize failed: {surface}'
    return surface

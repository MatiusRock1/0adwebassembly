#version 430

#include "common/compute.h"
#include "common/tone_mapper.h"

BEGIN_DRAW_TEXTURES
	TEXTURE_2D(0, inTex)
END_DRAW_TEXTURES

BEGIN_DRAW_UNIFORMS
	UNIFORM(vec4, screenSize)
	// Premultiplied exposure, already contains 2^exposure.
	UNIFORM(float, exposure)
END_DRAW_UNIFORMS

STORAGE_2D(0, rgba8, outTex);

layout(local_size_x = 8, local_size_y = 8, local_size_z = 1) in;
void main()
{
	ivec2 position = ivec2(gl_GlobalInvocationID.xy);
	if (any(greaterThanEqual(position, ivec2(screenSize.xy))))
		return;
	vec3 hdrColor = texelFetch(GET_DRAW_TEXTURE_2D(inTex), position, 0).rgb;
	vec3 sdrColor = applyTonemapper(hdrColor * exposure);
	imageStore(outTex, position, vec4(sdrColor, 1.0));
}

#version 120

#include "common/fragment.h"
#include "common/stage.h"
#include "common/tone_mapper.h"

BEGIN_DRAW_TEXTURES
	TEXTURE_2D(0, inTex)
END_DRAW_TEXTURES

BEGIN_DRAW_UNIFORMS
	// Premultiplied exposure, already contains 2^exposure.
	UNIFORM(float, exposure)
END_DRAW_UNIFORMS

VERTEX_OUTPUT(0, vec2, v_tex);

void main()
{
	vec3 hdrColor = SAMPLE_2D(GET_DRAW_TEXTURE_2D(inTex), v_tex).rgb;
	vec3 sdrColor = applyTonemapper(hdrColor * exposure);
	OUTPUT_FRAGMENT_SINGLE_COLOR(vec4(sdrColor, 1.0));
}

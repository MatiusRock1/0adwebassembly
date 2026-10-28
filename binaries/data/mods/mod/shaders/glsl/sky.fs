#version 110

#include "sky.h"

#include "common/fragment.h"

void main()
{
    vec3 color = SAMPLE_CUBE(GET_DRAW_TEXTURE_CUBE(baseTex), v_tex).rgb;

    float m = (1.0 - v_tex.y) - 0.75;
    m *= 4.0;

    OUTPUT_FRAGMENT_SINGLE_COLOR(vec4((v_tex.y > 0.0) ? clamp(color * m, 0.0, 1.0) : color, 1.0));
}

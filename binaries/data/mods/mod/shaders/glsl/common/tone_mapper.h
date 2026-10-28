#ifndef INCLUDED_COMMON_TONE_MAPPING
#define INCLUDED_COMMON_TONE_MAPPING

vec3 applyTonemapper(vec3 color)
{
	float whitePoint = 10.0;
	// Extendend Reinhard:
	// https://www-old.cs.utah.edu/docs/techreports/2002/pdf/UUCS-02-001.pdf
	return color * (vec3(1.0) + color / (whitePoint * whitePoint)) / (vec3(1.0) + color);
}

#endif // INCLUDED_COMMON_TONE_MAPPING

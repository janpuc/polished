#include <metal_stdlib>
#include <SwiftUI/SwiftUI_Metal.h>
using namespace metal;

// The tilt light on a painted tip (docs/NATIVE.md 4.4), applied to the painted layer only, inside
// the tip's clip: a specular pool that follows `light`, and a rainbow band across the 115 degree
// diagonal for the holographic finishes. Both are screened onto the premultiplied sample, so a
// strength of 0 (matte) returns the sample unchanged.

static float3 hsv2rgb(float3 c) {
  float3 p = abs(fract(c.xxx + float3(0.0, 2.0 / 3.0, 1.0 / 3.0)) * 6.0 - 3.0);
  return c.z * mix(float3(1.0), clamp(p - 1.0, 0.0, 1.0), c.y);
}

[[stitchable]] half4 tipLight(
    float2 pos, SwiftUI::Layer layer, float2 size, float2 light, float spec, float holo, float gloss) {
  half4 c = layer.sample(pos);  // premultiplied
  if (spec <= 0.0 && holo * gloss <= 0.0) return c;  // matte: the sample, untouched
  float2 uv = pos / size;
  float2 p = float2(0.5 + 0.4 * light.x, 0.5 + 0.4 * light.y);
  float2 d = (uv - p) / float2(0.30, 0.20);  // 60% by 40% ellipse
  float pool = spec * exp(-1.6 * dot(d, d));
  const float th = 115.0 * M_PI_F / 180.0;
  float t = uv.x * cos(th) + uv.y * sin(th);
  float centre = 0.5 + 0.3 * light.x;
  float w = 1.0 - smoothstep(0.0, 0.14, abs(t - centre));
  float hue = fract(0.9 * t + 0.35 * light.x + 0.15 * light.y);
  half3 rainbow = half3(hsv2rgb(float3(hue, 0.75, 1.0)));
  half3 room = half3(c.a) - c.rgb;
  half3 add = half(pool) * room + half(holo * w * gloss) * rainbow * room;
  return half4(c.rgb + add, c.a);
}

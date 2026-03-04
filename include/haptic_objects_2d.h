#pragma once

#include <math.h>

struct Vec2f {
  float x;
  float y;
};

inline Vec2f vec2_add(Vec2f a, Vec2f b) { return {a.x + b.x, a.y + b.y}; }
inline Vec2f vec2_scale(Vec2f a, float s) { return {a.x * s, a.y * s}; }
inline float vec2_dot(Vec2f a, Vec2f b) { return a.x * b.x + a.y * b.y; }

// Axis-aligned box in the same coordinates as (nX, nY) [meters].
// For an *obstacle* box: end-effector is allowed everywhere *except* inside this region.
struct HapticBox2D {
  float xmin;
  float xmax;
  float ymin;
  float ymax;

  // Penalty parameters for contact response.
  // - k: N/m stiffness (higher = harder wall)
  // - b: N/(m/s) damping along the contact normal (only when moving deeper)
  float k;
  float b;
};

inline Vec2f render_box_obstacle(const HapticBox2D &box, Vec2f p, Vec2f v) {
  // No contact if outside.
  if (p.x <= box.xmin || p.x >= box.xmax || p.y <= box.ymin || p.y >= box.ymax) {
    return {0.0f, 0.0f};
  }

  // Penetration depths to each face (positive since we are strictly inside).
  const float dLeft = p.x - box.xmin;
  const float dRight = box.xmax - p.x;
  const float dBottom = p.y - box.ymin;
  const float dTop = box.ymax - p.y;

  // Choose closest face => smallest distance to exit.
  float penetration = dLeft;
  Vec2f n = {-1.0f, 0.0f};

  if (dRight < penetration) {
    penetration = dRight;
    n = {1.0f, 0.0f};
  }
  if (dBottom < penetration) {
    penetration = dBottom;
    n = {0.0f, -1.0f};
  }
  if (dTop < penetration) {
    penetration = dTop;
    n = {0.0f, 1.0f};
  }

  // Spring term pushes outward.
  float fMag = box.k * penetration;

  // Damping term only when moving deeper into the obstacle.
  const float vN = vec2_dot(v, n);
  if (vN < 0.0f) {
    fMag += (-box.b * vN);
  }

  return vec2_scale(n, fMag);
}

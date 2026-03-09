//use this file to define the haptic objects in 2D space

#pragma once

//used for representing position or velocity of the end effector in 2D space, as well as forces to apply in 2D space
typedef struct Vector2{
    float x;
    float y;
} vector2_t;

//a point in 2d space
typedef struct Point{
    float x;
    float y;
} point_t;

typedef struct Line{
    point_t start;
    point_t end;
} line_t;

typedef struct Rect{
    point_t bottom_left;
    float width;
    float height;
} rect_t;

vector2_t computeForceForRect(rect_t rect, point_t end_effector_pos, vector2_t end_effector_vel){
    vector2_t force_to_apply = {0, 0};
    if (end_effector_pos.x < rect.bottom_left.x || end_effector_pos.x > rect.bottom_left.x + rect.width || end_effector_pos.y < rect.bottom_left.y || end_effector_pos.y > rect.bottom_left.y + rect.height)
    {
        return force_to_apply;
    }

    const float k = 500.0f; //spring constant
    const float b = 2.0f;   //damping

    const float distance_to_left = end_effector_pos.x - rect.bottom_left.x;
    const float distance_to_right = (rect.bottom_left.x + rect.width) - end_effector_pos.x;
    const float distance_to_bottom = end_effector_pos.y - rect.bottom_left.y;
    const float distance_to_top = (rect.bottom_left.y + rect.height) - end_effector_pos.y;

    // Choose closest face -> outward normal (nx, ny) and penetration depth (pen)
    float pen = distance_to_left;
    float nx = -1.0f;
    float ny = 0.0f;

    if (distance_to_right < pen) {
        pen = distance_to_right;
        nx = 1.0f;
        ny = 0.0f;
    }
    if (distance_to_bottom < pen) {
        pen = distance_to_bottom;
        nx = 0.0f;
        ny = -1.0f;
    }
    if (distance_to_top < pen) {
        pen = distance_to_top;
        nx = 0.0f;
        ny = 1.0f;
    }

    // Normal velocity component (positive when moving OUT along normal)
    const float v_n = end_effector_vel.x * nx + end_effector_vel.y * ny;

    // Unilateral spring + damping (don't let damping pull you back into the obstacle)
    float f_n = (k * pen) - (b * v_n);
    if (f_n < 0.0f) {
        f_n = 0.0f;
    }

    force_to_apply.x = f_n * nx;
    force_to_apply.y = f_n * ny;

    return force_to_apply;
}

vector2_t computeForceForLine(line_t line, point_t end_effector_pos, vector2_t end_effector_vel){
    return (vector2_t){0, 0};
}

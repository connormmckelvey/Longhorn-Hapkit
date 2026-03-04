//use this file to define the haptic objects in 2D space

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

vector2_t computeForceForRect(rect_t rect, point_t end_effector_pos, vector2_t end_effector_vel){}

vector2_t computeForceForLine(line_t line, point_t end_effector_pos, vector2_t end_effector_vel){}
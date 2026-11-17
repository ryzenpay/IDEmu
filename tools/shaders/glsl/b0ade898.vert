#version 120
attribute vec4 a_Position;
attribute vec4 a_Color;
attribute vec2 a_TextureCoordinate;
attribute vec2 a_TextureCoordinate1;
uniform mat4 u_MVPMatrix;
uniform float scale_right;
uniform float scale_top;
uniform float scale_bottom;
uniform float is_pie;
uniform float smll;
uniform float fade_squeeze;
uniform float fade_out;
uniform vec3 CO;
uniform vec3 CO_OUTLINE;
uniform vec3 CO_OUTLINE_EDGE;
uniform float lcm;
uniform float pressed;
varying vec2 uv;
varying vec2 pv;
varying vec3 c;
varying float vcm;
varying vec3 p_mppng;
void main(){
 vec4 P=a_Position;
 gl_Position=u_MVPMatrix*P;
 uv=a_TextureCoordinate;
 pv=a_TextureCoordinate1;
 vcm=a_Color.r;
 c=mix(CO,CO_OUTLINE,vcm);
 c=mix(c,CO_OUTLINE_EDGE,lcm);
 p_mppng=a_Color.rgb;
}

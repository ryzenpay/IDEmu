#version 120
attribute vec4 a_Position;
attribute vec2 a_TextureCoordinate;
uniform mat4 u_MVPMatrix;
uniform float limit;
uniform float speed;
varying vec2 uv;
varying float fade;
void main(){
 gl_Position=u_MVPMatrix*a_Position;
 uv=a_TextureCoordinate;
 fade=clamp(speed/max(abs(limit),0.0001),0.0,1.0);
}

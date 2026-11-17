#version 120
attribute vec4 a_Position;
attribute vec2 a_TextureCoordinate;
uniform mat4 u_MVPMatrix;
uniform float limit;
varying vec2 uv;
void main(){
 gl_Position=u_MVPMatrix*a_Position;
 uv=a_TextureCoordinate;
}

#version 120
attribute vec4 a_Position;
attribute vec2 a_TextureCoordinate;
attribute vec2 a_TextureCoordinate1;
uniform mat4 u_MVPMatrix;
varying vec4 varCoord;
void main(){
 gl_Position=u_MVPMatrix*a_Position;
 varCoord=vec4(a_TextureCoordinate,a_TextureCoordinate1);
}

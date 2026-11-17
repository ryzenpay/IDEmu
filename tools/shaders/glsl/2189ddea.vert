#version 120
attribute vec4 a_Position;
attribute vec2 a_TextureCoordinate;
uniform mat4 u_MVPMatrix;
varying vec2 varCoord;
void main(){
 gl_Position=u_MVPMatrix*a_Position;
 varCoord=a_TextureCoordinate;
}

#version 120
uniform sampler2D tex0;
uniform float opacity;
varying vec2 uv;
void main(){
 vec4 col=texture2D(tex0,uv);
 col.a*=opacity;
 gl_FragColor=col;
}

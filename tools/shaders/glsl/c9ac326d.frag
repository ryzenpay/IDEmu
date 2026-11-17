#version 120
uniform sampler2D tex0;
uniform sampler2D tex1;
uniform float value;
uniform float opacity;
varying vec4 varCoord;
void main(){
 vec4 inact=texture2D(tex0,varCoord.xy);
 vec4 act=texture2D(tex1,varCoord.xy);
 float on=step(varCoord.z,value);
 vec4 col=mix(inact,act,on);
 col.a*=opacity;
 gl_FragColor=col;
}

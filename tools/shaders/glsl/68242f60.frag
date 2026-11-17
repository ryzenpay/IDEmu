#version 120
uniform sampler2D tex0;
uniform float is_popup;
uniform float domain_opa;
uniform float focused;
uniform float opacity;
varying vec2 uv;
varying vec2 pv;
varying float vcm;
varying vec3 c;
varying vec3 p_mppng;
void main(){
 vec4 t=texture2D(tex0,uv);
 vec3 col=c*(0.35+0.65*t.r);
 col=mix(col,c,0.35*clamp(focused,0.0,1.0));
 float a=t.b;
 if(is_popup>0.5) a*=domain_opa;
 a*=opacity;
 gl_FragColor=vec4(col,a);
}

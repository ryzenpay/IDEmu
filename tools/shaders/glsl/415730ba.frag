#version 120
// mat_list_bg_mat_list_bg.frag (cursor/CursorBG = 415730ba) — fundo arredondado do cursor.
// O gerador ignorava bg_alpha/v_opacity (fade deascimento/morte do cursor) e entregava o
// mixed_co em alpha plena da textura. Aproximacao: forma pela textura * bg_alpha * opacidade.
uniform sampler2D tex0;
uniform float bg_alpha;
varying vec2 varCoord;
varying vec3 mixed_co;
varying float v_opacity;
void main(){
 vec4 t=texture2D(tex0,varCoord);
 float a=t.a*clamp(bg_alpha,0.0,1.0)*clamp(v_opacity,0.0,1.0);
 gl_FragColor=vec4(mixed_co,a);
}

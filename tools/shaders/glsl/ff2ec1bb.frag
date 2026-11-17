#version 120
// mat_list_top.frag (cursor/Cursor) — brilho superior do cursor da lista.
// O gerador por heuristica ignorava glowbirth/growth_u/p_inside (nascimento e forma da animacao)
// e entregava CO_HL na alpha total da textura: a FAIXA LARANJA OPACA sobre a linha focada.
// Aproximacao fiel: forma pela alpha da textura, multiplicada pelos fatores de animacao reais.
uniform sampler2D tex0;
uniform vec3 CO_HL;
uniform float opacity;
varying vec2 varCoord;
varying float glowbirth;
varying float growth_u;
varying float p_inside;
varying vec3 birth_params;
varying float v_active;
varying float ci;
void main(){
 float a=texture2D(tex0,varCoord).a;
 a*=clamp(glowbirth,0.0,1.0)*clamp(v_active,0.0,1.0)*clamp(growth_u,0.0,1.0)*clamp(1.0-p_inside,0.0,1.0);
 a*=clamp(opacity,0.0,1.0);
 gl_FragColor=vec4(CO_HL,a);
}

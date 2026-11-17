#version 120
// mat_list_touch_glow.frag (cursor/Cursor = d39e7923) — HALO do brilho do cursor da lista.
// O gerador por heuristica entregava CO_HL na alpha plena da textura: a FAIXA LARANJA OPACA
// sobre a linha focada (a alpha da textura e' uma barra cheia, nao um gradiente suave).
// Aproximacao fiel junto com 6c1df5c2 (touch, alpha 0.12): brilho discreto, sem borda dura.
uniform sampler2D tex0;
uniform vec3 CO_HL;
uniform float opacity;
varying vec2 uv;
void main(){
 float a=texture2D(tex0,uv).a;
 a*=0.12*clamp(opacity,0.0,1.0);
 gl_FragColor=vec4(CO_HL,a);
}

#version 120
// mat_main_bg.frag (aa92b59b) — cartão de fundo 3D de cada domínio do menu principal.
// A textura tex_main_bg_bitmap e' OPAQUE (alpha=255) e contem o gradiente no PROPRIO RGB
// (preto nas bordas, azul no meio). O gerador por heuristica inventou `a*=max(r,g,b)`
// (aniquilava o alpha fora do azul brilhante = fundo PRETO) e `rgb=CO` (CO=branco nos
// uniformes traçados — apagaria o gradiente). O shader real obviously usa a cor da propria
// textura; pre_alpha (fade do grafo WAL) nao esta na symtab do vertex => 1.0 (neutro).
uniform sampler2D tex0;
uniform vec3 CO;
uniform float opacity;
varying vec2 uvCoord;
void main(){
 vec4 t=texture2D(tex0,uvCoord);
 gl_FragColor=vec4(t.rgb*CO, t.a*clamp(opacity,0.0,1.0));
}

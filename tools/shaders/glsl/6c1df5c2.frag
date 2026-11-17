#version 120
// mat_list_touch_mat_list_touch.frag (cursor/Cursor = prog 155) — brilho do cursor da lista. No hardware e um glow sutil e
// translucido na linha focada; o gerador por heuristica (sem binario decompilado) entregava um
// LARGO opaco (a faixa laranja sobre a lista). alpha 0.12 ate existir decompilador USC.
varying vec4 col;
void main(){
 gl_FragColor=vec4(col.rgb,0.12);
}

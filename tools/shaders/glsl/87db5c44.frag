#version 120
// WI_Streamline1.frag (87db5c44) + WI_StreamlineR1.frag (5cb626ec) — o binario SGX faz reflexo de
// cubemap (CubeMapTex/R/worldZ) sobre o vertice colorido do controller. O host nunca recebe o
// cubemap (nenhum glTexImage de cubemap na traca): amostraria preto. O gerador por heuristica
// sombreava o varying "col" com o local e cuspia BRANCO OPAQUE — a mancha branca que cobria o
// wallpaper do menu e os paineis. Transparente e a saida honesta ate existir um decompilador USC.
varying vec4 col;
void main(){
 gl_FragColor=vec4(col.rgb,0.0);
}

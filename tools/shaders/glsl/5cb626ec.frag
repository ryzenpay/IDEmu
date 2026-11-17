#version 120
// irma do 87db5c44 (WI_StreamlineGlows.frag): mesmo cubemap inexistente no host -> transparente.
varying vec4 col;
void main(){
 gl_FragColor=vec4(col.rgb,0.0);
}

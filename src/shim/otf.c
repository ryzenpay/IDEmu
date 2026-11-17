/* Fake libBMWOTFapi.so.3 : no agent; prints the HMI's trace text to the host log */
#include "common.h"
typedef __builtin_va_list va_list;
#define va_start __builtin_va_start
#define va_end __builtin_va_end
extern int vsnprintf(char*,unsigned long,const char*,va_list);
extern int snprintf(char*,unsigned long,const char*,...);
extern char *strstr(const char*,const char*);
extern unsigned long strlen(const char*);
#include "otf_stubs.inc"
unsigned guiStartTime;
/* nivel dos bits de traco forcados em todo scope OTF. 0x10 basta para T/E/W; subir para 0x3f expoe os scopes
   "verbosos" do framework (HmiServices_CSvcFunctionProxy_sendMsg/clr0/clr1 etc.) — diagnostico do por que
   o HMI nunca assina CEngineSpeed2/Torque2/Pedal2 (05.00 cd0/cd1/cd3). */
#ifndef OTFLVL
#define OTFLVL 0x10
#endif
void *_ZN15OTF_CppScopeUseC1EPK17tagOTF_ScopeEntry(void **t,void *s){ *t=s; return t; }
void *_ZN15OTF_CppScopeUseC2EPK17tagOTF_ScopeEntry(void **t,void *s){ *t=s; return t; }
void *_ZN15OTF_CppScopeUseD1Ev(void *t){ return t; }
void *_ZN15OTF_CppScopeUseD2Ev(void *t){ return t; }
typedef struct { u32 id; const char *name; u32 a,b; u16 c,d; u8 lvl; } scope_t;
static int prefix(const char*s,const char*p){ while(*p) if(*s++!=*p++) return 0; return 1; }
static u32 s_act, s_emits, s_deadline;
static void sportdump(void);
/* cada br_log Ã© uma ida e volta sincrona pelo bridge (para a VM inteira); a id5+ dispara milhares de
   asserts por boot (CGfxScript) e a mesma linha repete ~10x/s. Mesma linha em 15 s => suprimida, e o
   total aparece no sufixo "(+N em 15s)" da proxima que passar. Competicao por tabela = diagnostico, benigna. */
extern int clock_gettime(int,void*);
typedef struct { u32 key, last, n; } thr_t;
static thr_t thr[128];
static u32 now_ms(void){ u32 ts[2]={0,0}; clock_gettime(2,ts); return ts[0]*1000u+ts[1]/1000000u; }
static void emit(const char *lvl,scope_t *s,const char *msg){ char b[300]; const char*nm="?"; if((u32)s>0x1000&&s->name&&(u32)s->name>0x1000) nm=s->name;
  s_emits++;
  if(msg){ const char *a=strstr(msg,"CCarInstrumentsOfSportActivity [");
    if(a && !s_act){ a+=30; while(*a && *a!='[') a++; if(*a=='[') a++; u32 v=0;
      for(;*a&&*a!=']';a++){ int c=(*a>='0'&&*a<='9')?*a-'0':(((*a|32)>='a'&&(*a|32)<='f')?(*a|32)-'a'+10:-1); if(c<0)break; v=v*16+c; }
      if(v>0x1000){ s_act=v; char ar[40]; snprintf(ar,sizeof ar,"SDUMP armed act=%08x",v); br_log(ar); } }
    if(strstr(msg,"FktIDs=C7A")||strstr(msg,"FktIDs=C7B")) s_deadline=s_emits+30;
  }
  if((s_deadline&&s_emits>=s_deadline) || (s_act&&s_emits%200000u==0)) sportdump();
  if(lvl[0]=='T'&&(prefix(nm,"HmiBase_CHmiTimer")||prefix(nm,"A4A_")||prefix(nm,"CommonAPI_")||prefix(nm,"HmiBase_ProfTime")||prefix(nm,"CHmiResourceManager")||prefix(nm,"HmiPerformanceMonitor")||prefix(nm,"HmiPlugin_")||prefix(nm,"Hmi_Ines_textureCreate"))) return; snprintf(b,sizeof b,"%s[%s] %s",lvl,nm,msg?msg:"(null)");
  u32 h=5381; const char*p; for(p=b;*p;p++) h=h*33+(u8)*p;
  thr_t*e=&thr[h&127]; u32 t=now_ms(), sup=0;
  if(e->key==h&&t-e->last<15000){ e->n++; return; }
  if(e->key==h){ sup=e->n; }
  e->key=h; e->last=t; e->n=0;
  if(sup>1){ char c[340]; snprintf(c,sizeof c,"%s (+%u em 15s)",b,sup); br_log(c); } else br_log(b); }
extern void install_hooks(void);
int OTF_open(const char*a,const char*b,u32 c,u32 d){ br_log("OTF_open(fake)"); install_hooks(); return 1; }

/* ---- sondagem viva do Sport displays (diagnostico do layout c7a/c7b) --------------------
   A lifecycle trace do HMI entrega o endereco do objeto da atividade ("... [906a648] ...").
   A partir dele andamos o grafo que a atividade usa no update (0x9e88c0 no HmiMain3D):
     dev = *(act+0xb8);  eng = *(dev+8);  vtbl = *eng;  r14 = vtbl[+0x14](eng); r18 = vtbl[+0x18](eng)
   param_power = r14*0.01, param_torque = r18*0.01 (constante 0.01 no proprio update).
   O dump dispara ~30 emits depois de uma notificacao C7A/C7B (nosso push) — depois do handler
   de decode rodar — e mostra os membros crus do objeto e dos 3 proxies assinados (pxy+0x3764,
   +0x37f0, +0x5108), deixando ligar cada byte do Status ao valor que o getter devolve. */
static u32 rdw(u32 a){ return *(u32*)a; }
static void sportdump(void){
  if(!s_act) return;
  if(s_deadline && (s_emits<s_deadline || s_emits>s_deadline+3000000u)) return;   /* dump único por janela */
  s_deadline=0;
  if(s_act<0x1000||s_act>0xf0000000u) return;
  u32 dev=rdw(s_act+0xb8);
  char b[320];
  if(dev<0x1000||dev>0xf0000000u){ snprintf(b,sizeof b,"SDUMP act=%08x dev=%08x (ruim)",s_act,dev); br_log(b); return; }
  u32 eng=rdw(dev+8);
  if(eng<0x1000||eng>0xf0000000u){ snprintf(b,sizeof b,"SDUMP act=%08x dev=%08x eng=%08x (ruim)",s_act,dev,eng); br_log(b); return; }
  u32 vt=rdw(eng), f14=vt<0x1000?0:rdw(vt+0x14), f18=vt<0x1000?0:rdw(vt+0x18);
  int r14=-1,r18=-1;
  if(f14>0x100000&&f14<0x3900000) r14=((int(*)(void*))f14)((void*)eng);
  if(f18>0x100000&&f18<0x3900000) r18=((int(*)(void*))f18)((void*)eng);
  snprintf(b,sizeof b,"SDUMP dev=%08x eng=%08x r14=%d r18=%d",dev,eng,r14,r18);
  u32 ep=rdw(eng+0x28);   /* m_pPxyVehicle visto pelo getter (this=eng-0x18, +0x40) */
  snprintf(b+strlen(b),sizeof b-strlen(b)," ep=%08x pxy=%08x",ep,rdw(dev+0x40));
  if(ep>0x1000&&ep<0xf0000000u){
    u32 acc=ep+0x37a4; int flg=-1,rv1=-1,rv2=-1; u8 v1=0,v2=0;
    if(acc>0x1000&&acc<0xf0000000u){
      flg=((int(*)(void*))0x2191910)((void*)acc);
      rv1=((int(*)(void*,void*))0x2472bf4)((void*)acc,&v1);
      rv2=((int(*)(void*,void*))0x2472c30)((void*)acc,&v2);
    }
    snprintf(b+strlen(b),sizeof b-strlen(b)," flg=%d p=%d,%d t=%d,%d h=",flg,rv1,v1,rv2,v2);
    u8 *w=(u8*)(ep+0x3800);
    for(int j=0;j<32&&strlen(b)<200;j++) snprintf(b+strlen(b),sizeof b-strlen(b),"%02x",w[j]);
  }
  br_log(b);
}
int OTF_traceV(scope_t *s,const char *f,va_list ap){ char t[256]; vsnprintf(t,sizeof t,f,ap); t[255]=0; emit("T",s,t); return 0; }
int OTF_trace(scope_t *s,const char *f,...){ va_list ap; va_start(ap,f); OTF_traceV(s,f,ap); va_end(ap); return 0; }
int OTF_error(scope_t *s,const char *m){ emit("E",s,m); return 0; }
int OTF_warning(scope_t *s,const char *m){ emit("W",s,m); return 0; }
u32 OTF_getUIntSetting(u32 a,u32 b){ return b; }
/* scope ctor: same layout as the real one, no registration */
void *_ZN17OTF_CppScopeEntryC2EPKch(scope_t *t,const char *n,u8 lvl){ t->id=0; t->name=n; t->a=t->b=0; t->c=t->d=0; t->lvl=(lvl&~3)|OTFLVL; return t; }
void *_ZN17OTF_CppScopeEntryC1EPKch(scope_t *t,const char *n,u8 lvl){ return _ZN17OTF_CppScopeEntryC2EPKch(t,n,lvl); }

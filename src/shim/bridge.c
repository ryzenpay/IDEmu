#include "common.h"
volatile int br_lock_v;
static volatile u32 *R; static u32 *Q,*P; static u32 qn; static int inited,dummy;
static u32 dummyrep[4];
#ifdef CRASHHK
/* diagnóstico (-DCRASHHK): tabela tid->(SP, último op) das threads que passam pela ponte; o host pede o despejo
   pelo evento 62 (arquivo <ctl>/shimdbg.req). Nunca no shim de produção. */
static void brk_note(u32 op);
#endif
#define QCAP (2*1024*1024)
void br_init(void){
  if(inited) return; inited=1;
  R=(volatile u32*)mmap_device_memory(0,0x1000,0xb00,0,0x7ff00000ULL);
  u32 *b=(u32*)mmap_device_memory(0,0x1000000,0x300,0,0x7e000000ULL);
  if((int)R==-1||(int)b==-1){ dummy=1; Q=(u32*)malloc(8<<20); P=dummyrep; }
  else { Q=b; P=b+0x200000; }
}
u32 *br_begin(u32 op,u32 n){
#ifdef CRASHHK
  brk_note(op);
#endif
  if(qn+2+n>QCAP-8) br_flush();
  u32 *p=Q+qn; p[0]=op; p[1]=n; qn+=2+n; return p+2;
}
void br_flush(void){
  if(!qn) return;
  if(dummy){ qn=0; dummyrep[0]=0; return; }
  u32 n=qn*4; qn=0; R[0]=n;
}
u32 br_sync(u32 **rep){
  br_flush(); *rep=P;
  if(dummy) return 0;
  return R[2];
}
static void putstr(const char*s,u32 a,u32 b,u32 c){
  u32 l=strlen(s); u32 nw=(l+3)/4;
  u32 *p=br_begin(OP_LOG,4+nw); p[0]=l; p[1]=a; p[2]=b; p[3]=c; memcpy(p+4,s,l);
}
void br_logx(const char*s,u32 a,u32 b,u32 c){ LOCK(); putstr(s,a,b,c); br_flush(); UNLOCK(); }
void br_log(const char*s){ br_logx(s,0,0,0); }
#ifdef CRASHHK
/* log SEM o lock: para o handler de SIGSEGV (a thread pode ter morrido DENTRO da seção crítica, segurando br_lock_v para sempre) */
void br_logx_nl(const char*s,u32 a,u32 b,u32 c){ putstr(s,a,b,c); br_flush(); }
#endif
#ifdef CRASHHK
extern int gettid(void);
volatile u32 brk_holder_tid, brk_lock_ops;
static u32 brk_tab_[64][4];   /* tid, SP de quem chamou a ponte, último op, n (a pilha real pode ter aprofundado desde então) */
static void brk_note(u32 op){ u32 tid=(u32)gettid(),sp=(u32)__builtin_frame_address(2);
  brk_lock_ops=op;
  for(int i=0;i<64;i++){ if(brk_tab_[i][0]==tid||!brk_tab_[i][0]){ brk_tab_[i][0]=tid; brk_tab_[i][1]=sp; brk_tab_[i][2]=op; brk_tab_[i][3]++; return; } } }
u32 *brk_tab(u32 *n){ *n=0; while(*n<64&&brk_tab_[*n][0]) (*n)++; return &brk_tab_[0][0]; }
u32 brk_qn(void){ return qn; }                    /*Words já montadas da chamada em andamento (para o QDUMP do crash_h) */
u32 brk_qw(u32 i){ return i<QCAP?Q[i]:0; }
static u32 snap[260], snapn;                      /* foto read-only da chamada em andamento (o cabeçalho já está no lote anterior: não descartar, senão a ponte executaria de novo) */
void brk_snap(void){ snapn=qn; u32 n=qn<260?qn:260; for(u32 i=0;i<n;i++) snap[i]=Q[i]; }
u32 brk_snapw(u32 i){ return i<260?snap[i]:0; }
u32 brk_snapn(void){ return snapn; }
/* dono do lock + op em voo (para o watchdog): gravados logo após adquirir o lock, sem custo de sincronização */
void brk_set_hold(u32 op){ extern int gettid(void); brk_holder_tid=(u32)gettid(); brk_lock_ops=op; }
void brk_set_rel(void){ brk_holder_tid=0; brk_lock_ops=0; }
void brk_note_op(u32 op){ brk_lock_ops=op; }        /* chamado por brk_note (sob o lock): op em voo real */
u32 brk_qn_ptr(void){ return qn; }
u32 brk_dummy(void){ return (u32)dummy; }
/* Watchdog: thread próprio (stack padrão), heartbeat por MMIO puro (R[4] → qemu.log "IDEMU_WD") —
   sem lock, sem socket, sem bridge. Sobrevive a QUALQUER travamento da ponte e identifica o dono do lock. */
extern int pthread_create(void*,const void*,void*(*)(void*),void*);
extern int getpid(void);
static void *wd_thread(void *a){ u32 k=0; extern volatile int br_lock_v; extern volatile u32 brk_holder_tid,brk_lock_ops;
  u32 pid=(u32)getpid(), mytid; { extern int gettid(void); mytid=(u32)gettid(); }
  for(;;){ usleep(2000000);
    if(!inited||dummy) continue;
    u32 pc; __asm__ volatile("bl 1f\n1: mov %0, lr\n":"=r"(pc));
    R[4]=0x1000000u|(k++&0xffffff);                           /* WD0: tick */
    R[4]=0x1100000u|((u32)(br_lock_v?1:0)<<16)|(brk_holder_tid&0xffff);   /* WD1: lock+16, dono (16 bits baixos) */
    R[4]=0x1200000u|(brk_qn_ptr()&0xfffff);                   /* WD2: qn em andamento */
    R[4]=0x1300000u|(((pc>>12))&0xfffff);                     /* WD3: pc do watchdog (20 altos) */
    R[4]=0x1400000u|(pid&0xfffff);                            /* WD4: pid | dono>>16 (2 linhas abaixo, separado) */
    R[4]=0x1500000u|((brk_holder_tid>>16)&0xffff);            /* WD5: dono (16 altos) */
    R[4]=0x1600000u|(mytid&0xfffff);                          /* WD6: tid do próprio watchdog (escala) */
    R[4]=0x1700000u|(brk_lock_ops&0xfffff);                   /* WD7: último op montado sob o lock atual */
    (void)pc; } }
void brk_wd_start(void){ static int started; if(!started){ started=1; static u32 tid; pthread_create(tid,0,wd_thread,0); } }
#endif

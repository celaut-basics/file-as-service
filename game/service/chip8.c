/* Classic CHIP-8 interpreter. Original implementation, no ROM downloads.
 * stdin: 2-byte big-endian held-key mask, 60 ticks/s driven by service.
 * stdout: 2048 monochrome pixel bytes + one sound-timer byte per tick.
 * COSMAC-style shifts (Vy), I increments on Fx55/Fx65, wrapped sprites.
 * SCHIP/XO-CHIP deliberately unsupported; invalid opcodes fail closed.
 */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
static uint8_t m[4096],v[16],screen[2048],delay,sound;
static uint16_t pc=512,I,stack[16],keys;static unsigned sp;
static const uint8_t font[]={
0xf0,0x90,0x90,0x90,0xf0,0x20,0x60,0x20,0x20,0x70,
0xf0,0x10,0xf0,0x80,0xf0,0xf0,0x10,0xf0,0x10,0xf0,
0x90,0x90,0xf0,0x10,0x10,0xf0,0x80,0xf0,0x10,0xf0,
0xf0,0x80,0xf0,0x90,0xf0,0xf0,0x10,0x20,0x40,0x40,
0xf0,0x90,0xf0,0x90,0xf0,0xf0,0x90,0xf0,0x10,0xf0,
0xf0,0x90,0xf0,0x90,0x90,0xe0,0x90,0xe0,0x90,0xe0,
0xf0,0x80,0x80,0x80,0xf0,0xe0,0x90,0x90,0x90,0xe0,
0xf0,0x80,0xf0,0x80,0xf0,0xf0,0x80,0xf0,0x80,0x80};
static void fail(void){fputs("Invalid/unsupported CHIP-8 instruction or memory access\n",stderr);exit(2);}
static void step(void){
 if(pc>4094)fail();unsigned op=(m[pc]<<8)|m[pc+1],x=(op>>8)&15,y=(op>>4)&15,n=op&15,nn=op&255,nnn=op&4095;pc+=2;
 switch(op>>12){
 case 0:if(op==0x00e0)memset(screen,0,sizeof screen);else if(op==0x00ee){if(!sp)fail();pc=stack[--sp];}else fail();break;
 case 1:pc=nnn;break;
 case 2:if(sp==16)fail();stack[sp++]=pc;pc=nnn;break;
 case 3:if(v[x]==nn)pc+=2;break;
 case 4:if(v[x]!=nn)pc+=2;break;
 case 5:if(n)fail();if(v[x]==v[y])pc+=2;break;
 case 6:v[x]=nn;break;
 case 7:v[x]+=nn;break;
 case 8:{unsigned a=v[x],b=v[y];switch(n){
 case 0:v[x]=b;break;case 1:v[x]=a|b;v[15]=0;break;case 2:v[x]=a&b;v[15]=0;break;case 3:v[x]=a^b;v[15]=0;break;
 case 4:v[x]=a+b;v[15]=(a+b)>255;break;case 5:v[x]=a-b;v[15]=a>=b;break;
 case 6:v[x]=b>>1;v[15]=b&1;break;case 7:v[x]=b-a;v[15]=b>=a;break;
 case 14:v[x]=b<<1;v[15]=b>>7;break;default:fail();}break;}
 case 9:if(n)fail();if(v[x]!=v[y])pc+=2;break;
 case 10:I=nnn;break;case 11:pc=nnn+v[0];break;case 12:v[x]=(rand()&255)&nn;break;
 case 13:{unsigned px=v[x],py=v[y];if(!n||I+n>4096)fail();v[15]=0;for(unsigned row=0;row<n;row++)for(unsigned bit=0;bit<8;bit++)if(m[I+row]&(128>>bit)){unsigned pos=((py+row)%32)*64+(px+bit)%64;v[15]|=screen[pos];screen[pos]^=1;}break;}
 case 14:if(v[x]>15)fail();if(nn==0x9e){if(keys&(1u<<v[x]))pc+=2;}else if(nn==0xa1){if(!(keys&(1u<<v[x])))pc+=2;}else fail();break;
 case 15:switch(nn){
 case 7:v[x]=delay;break;case 10:{unsigned k;for(k=0;k<16;k++)if(keys&(1u<<k))break;if(k==16)pc-=2;else v[x]=k;break;}
 case 21:delay=v[x];break;case 24:sound=v[x];break;case 30:I+=v[x];break;
 case 41:if(v[x]>15)fail();I=v[x]*5;break;
 case 51:if(I+2>=4096)fail();m[I]=v[x]/100;m[I+1]=(v[x]/10)%10;m[I+2]=v[x]%10;break;
 case 85:if(I+x>=4096)fail();memcpy(m+I,v,x+1);I+=x+1;break;
 case 101:if(I+x>=4096)fail();memcpy(v,m+I,x+1);I+=x+1;break;
 default:fail();}break;
 default:fail();
 }
}
int main(int argc,char **argv){if(argc!=2)return 1;FILE *f=fopen(argv[1],"rb");if(!f)return 1;
 size_t size=fread(m+512,1,3584,f);int extra=fgetc(f);fclose(f);if(!size||extra!=EOF)return 1;memcpy(m,font,sizeof font);
 int a,b;while((a=getchar())!=EOF&&(b=getchar())!=EOF){keys=(a<<8)|b;for(int i=0;i<10;i++)step();
 if(fwrite(screen,1,2048,stdout)!=2048||putchar(sound)==EOF||fflush(stdout))return 1;
 if(delay)delay--;if(sound)sound--;}
 return 0;}

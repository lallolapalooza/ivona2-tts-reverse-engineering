
// ----- 00048ca0 : queried -----
// function: FUN_00048ca0 @ 00048ca0

undefined4 FUN_00048ca0(int param_1,char *param_2,char *param_3,char *param_4,int *param_5)

{
  int iVar1;
  char *__s2;
  int *piVar2;
  
  piVar2 = &DAT_001901a8;
  __s2 = "eng_max_sentence";
  do {
    iVar1 = strcmp(param_3,__s2);
    if (iVar1 == 0) {
      if (__s2 != (char *)0x0) {
        iVar1 = strcmp(param_2,"set");
        if (iVar1 == 0) {
          if (param_4 != (char *)0x0) {
            iVar1 = strcmp(param_4,"min");
            if (iVar1 != 0) {
              strcmp(param_4,"max");
              FUN_0005af6c(*(undefined4 *)**(undefined4 **)(param_1 + 0x14),param_3);
              return 1;
            }
            FUN_0005af6c(*(undefined4 *)**(undefined4 **)(param_1 + 0x14),param_3,piVar2[1]);
            return 1;
          }
          if ((piVar2[1] <= *param_5) && (*param_5 <= piVar2[2])) {
            FUN_0005af6c(*(undefined4 *)**(undefined4 **)(param_1 + 0x14),param_3);
            return 1;
          }
          FUN_000474e4(6);
          return 0;
        }
        iVar1 = strcmp(param_2,"get");
        if (iVar1 == 0) {
          if (param_4 == (char *)0x0) {
            iVar1 = FUN_0005b230(*(undefined4 *)**(undefined4 **)(param_1 + 0x14),param_3,0);
            *param_5 = iVar1;
            return 1;
          }
          iVar1 = strcmp(param_4,"min");
          if (iVar1 != 0) {
            iVar1 = strcmp(param_4,"max");
            if (iVar1 == 0) {
              *param_5 = piVar2[2];
            }
            else {
              *param_5 = piVar2[3];
            }
            return 1;
          }
          *param_5 = piVar2[1];
        }
        return 1;
      }
      break;
    }
    piVar2 = piVar2 + 4;
    __s2 = (char *)*piVar2;
  } while (__s2 != (char *)0x0);
  FUN_00047500(10,"Invalid length param");
  return 0;
}



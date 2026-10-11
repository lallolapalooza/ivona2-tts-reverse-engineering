
// ----- 0001f1d4 : queried -----
// function: FUN_0001f1d4 @ 0001f1d4

/* WARNING: Control flow encountered bad instruction data */

void FUN_0001f1d4(void)

{
                    /* WARNING: Bad instruction - Truncating control flow here */
  halt_baddata();
}



// ----- 0001f1d4 : queried -----
// function: FUN_0001f1d4 @ 0001f1d4

/* WARNING: Control flow encountered bad instruction data */

void FUN_0001f1d4(void)

{
                    /* WARNING: Bad instruction - Truncating control flow here */
  halt_baddata();
}



// ----- 0001f1d4 : queried -----
// function: FUN_0001f1d4 @ 0001f1d4

void FUN_0001f1d4(int param_1)

{
  __time_t _Var1;
  __time_t _Var2;
  long lVar3;
  long lVar4;
  int iVar5;
  undefined4 uVar6;
  undefined4 uVar7;
  int iVar8;
  int iVar9;
  pthread_mutex_t *__mutex;
  uint uVar10;
  uint uVar11;
  uint uVar12;
  int iStack_48;
  int iStack_44;
  void *pvStack_40;
  int iStack_38;
  int iStack_28;
  uint uStack_24;
  timespec tStack_20;
  
  iVar5 = FUN_000233d0();
  if (iVar5 == 0) {
    __android_log_print(6,"IVONATTS","Failed to get voice handle.");
  }
  else {
    uVar10 = 0;
    *(undefined4 *)(param_1 + 0x68) = 0;
    uVar11 = 0;
    iStack_48 = 0;
    pvStack_40 = (void *)0x0;
    while (iVar9 = *(int *)(param_1 + 0x68), *(char *)(param_1 + 0x50) != '\0') {
      if ((iVar9 != 0) && (iVar9 != *(int *)(param_1 + 0x54))) {
        (**(code **)(iVar5 + 0x5c))();
        uVar11 = 0;
        FUN_0001ee14(param_1);
        *(undefined4 *)(param_1 + 0x68) = 0;
      }
      iStack_44 = iStack_48;
      if (*(int *)(param_1 + 0x68) == 0) {
        __mutex = (pthread_mutex_t *)(param_1 + 0x48);
        pthread_mutex_lock(__mutex);
        *(int *)(param_1 + 0x68) = *(int *)(param_1 + 0x54);
        if (*(int *)(param_1 + 0x54) == 0) {
          clock_gettime(0,&tStack_20);
          tStack_20.tv_sec = tStack_20.tv_sec + 1;
          pthread_cond_timedwait((pthread_cond_t *)(param_1 + 0x4c),__mutex,&tStack_20);
        }
        pthread_mutex_unlock(__mutex);
        if (*(undefined4 **)(param_1 + 0x68) != (undefined4 *)0x0) {
          iStack_44 = (**(code **)(iVar5 + 0x34))(**(undefined4 **)(param_1 + 0x68));
          if (iStack_44 != iStack_48) {
            uVar6 = __floatunsisf();
            __mulsf3(uVar6,0x3e99999a);
            iStack_38 = __fixunssfsi();
            if (pvStack_40 != (void *)0x0) {
              operator_delete(pvStack_40);
            }
            pvStack_40 = operator_new__(iStack_38 << 1);
            __mulsf3(uVar6,0x40400000);
            uVar6 = __fixunssfsi();
            FUN_0001f048(param_1 + 8,uVar6,iStack_38);
          }
          goto LAB_0001f2b0;
        }
      }
      else {
LAB_0001f2b0:
        if (uVar11 == 0) {
          if (1 < *(int *)(param_1 + 0x5c)) {
            uStack_24 = (uint)(*(int *)(param_1 + 0x5c) == 3);
            iVar9 = (**(code **)(iVar5 + 0x30))
                              (*(undefined4 *)(param_1 + 0x58),"set:contrast",&uStack_24);
            if (iVar9 != 1) {
              uVar6 = (**(code **)(iVar5 + 8))();
              __android_log_print(5,"IVONATTS","could not set contrast: %s",uVar6);
            }
            *(uint *)(param_1 + 0x5c) = (uint)(uStack_24 == 1);
          }
          func_0x0001bccc(&tStack_20,0);
          lVar3 = tStack_20.tv_nsec;
          _Var1 = tStack_20.tv_sec;
          if (*(char *)(param_1 + 0x60) == '\0') {
            uVar12 = (**(code **)(iVar5 + 0x68))
                               (*(undefined4 *)(param_1 + 0x68),pvStack_40,iStack_38);
            if (uVar12 == 0) {
LAB_0001f336:
              pthread_mutex_lock((pthread_mutex_t *)(param_1 + 0x48));
              if (*(int *)(param_1 + 0x68) == *(int *)(param_1 + 0x54)) {
                *(undefined4 *)(param_1 + 0x54) = 0;
              }
              pthread_mutex_unlock((pthread_mutex_t *)(param_1 + 0x48));
              (**(code **)(iVar5 + 0x5c))(*(undefined4 *)(param_1 + 0x68));
              *(undefined4 *)(param_1 + 0x68) = 0;
              pthread_cond_broadcast((pthread_cond_t *)(param_1 + 0xc));
              if (*(char *)(param_1 + 0x60) != '\0') {
                pthread_cond_broadcast((pthread_cond_t *)(param_1 + 0x2c));
              }
              goto LAB_0001f446;
            }
          }
          else {
            iStack_28 = (**(code **)(iVar5 + 0x6c))
                                  (*(undefined4 *)(param_1 + 0x68),*(undefined4 *)(param_1 + 100));
            if (iStack_28 == 0) {
              iVar9 = (**(code **)(iVar5 + 4))();
              if (iVar9 == 0) goto LAB_0001f336;
              uVar12 = 0xffffffff;
            }
            else {
              uVar12 = 1;
            }
          }
          func_0x0001bccc(&tStack_20,0);
          lVar4 = tStack_20.tv_nsec;
          _Var2 = tStack_20.tv_sec;
          uVar11 = uVar12;
          if (*(char *)(param_1 + 0x60) == '\0') {
            uVar6 = __floatunsisf(*(undefined4 *)(param_1 + 0x18));
            uVar7 = __floatunsisf(iStack_44 << 1);
            uVar7 = __mulsf3(uVar7,0x3e99999a);
            iVar9 = __aeabi_fcmpgt(uVar6,uVar7);
            if (iVar9 != 0) {
              iVar9 = __divsi3(lVar4);
              iVar8 = __divsi3(lVar3,1000);
              uVar6 = __floatsisf((_Var2 * 1000 + iVar9) - (_Var1 * 1000 + iVar8));
              __subsf3(0x43160000,uVar6);
              iVar9 = __fixsfsi();
              if (0 < iVar9) {
                usleep(iVar9 * 1000);
              }
            }
          }
        }
        if ((uVar10 < uVar11) && (*(int *)(param_1 + 0x68) == *(int *)(param_1 + 0x54))) {
          if (*(char *)(param_1 + 0x60) == '\0') {
            iVar9 = func_0x0001f12c(param_1 + 8,(void *)((int)pvStack_40 + uVar10 * 2),
                                    uVar11 - uVar10);
          }
          else {
            iVar9 = FUN_0001f084(param_1 + 0x28,&iStack_28,1);
          }
          uVar10 = uVar10 + iVar9;
          if (uVar10 == uVar11) {
            uVar10 = 0;
            uVar11 = 0;
          }
        }
      }
LAB_0001f446:
      iStack_48 = iStack_44;
    }
    if (iVar9 != 0) {
      (**(code **)(iVar5 + 0x5c))();
      *(undefined4 *)(param_1 + 0x68) = 0;
    }
    if (pvStack_40 != (void *)0x0) {
      operator_delete__(pvStack_40);
    }
    FUN_0001ee14(param_1);
  }
  return;
}



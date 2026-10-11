
// ----- 00077db8 : queried -----
// function: FUN_00077cb8 @ 00077cb8

bool FUN_00077cb8(int param_1,undefined4 param_2,uint param_3,uint param_4)

{
  int iVar1;
  uint uVar2;
  bool bVar3;
  
  iVar1 = param_1;
  if (param_1 < 0) {
    iVar1 = param_1 + 0x7f;
  }
  iVar1 = (uint)*(ushort *)
                 (&DAT_001675b0 +
                 ((uint)(byte)(&DAT_001653b0)[iVar1 >> 7] * 0x80 + param_1 % 0x80) * 2) * 8;
  switch(param_2) {
  case 1:
    if ((((&DAT_00164381)[iVar1] == '\t') || ((&DAT_00164381)[iVar1] == '\x05')) ||
       ((&DAT_00164381)[iVar1] == '\b')) {
      uVar2 = 1;
    }
    else {
      uVar2 = 0;
    }
    bVar3 = uVar2 == param_4;
    break;
  case 2:
    bVar3 = (*(uint *)(&DAT_00163c28 + (uint)(byte)(&DAT_00164381)[iVar1] * 4) == param_3) ==
            param_4;
    break;
  case 3:
    bVar3 = ((byte)(&DAT_00164381)[iVar1] == param_3) == param_4;
    break;
  case 4:
    bVar3 = ((byte)(&DAT_00164380)[iVar1] == param_3) == param_4;
    break;
  case 5:
    if ((*(int *)(&DAT_00163c28 + (uint)(byte)(&DAT_00164381)[iVar1] * 4) == 1) ||
       (*(int *)(&DAT_00163c28 + (uint)(byte)(&DAT_00164381)[iVar1] * 4) == 3)) {
      uVar2 = 1;
    }
    else {
      uVar2 = 0;
    }
    bVar3 = uVar2 == param_4;
    break;
  case 6:
    if ((((*(int *)(&DAT_00163c28 + (uint)(byte)(&DAT_00164381)[iVar1] * 4) == 6) || (param_1 == 9))
        || (param_1 == 10)) || ((param_1 == 0xc || (param_1 == 0xd)))) {
      uVar2 = 1;
    }
    else {
      uVar2 = 0;
    }
    bVar3 = uVar2 == param_4;
    break;
  case 7:
    if ((((*(int *)(&DAT_00163c28 + (uint)(byte)(&DAT_00164381)[iVar1] * 4) == 6) || (param_1 == 9))
        || ((param_1 == 10 || ((param_1 == 0xb || (param_1 == 0xc)))))) || (param_1 == 0xd)) {
      uVar2 = 1;
    }
    else {
      uVar2 = 0;
    }
    bVar3 = uVar2 == param_4;
    break;
  case 8:
    if (((*(int *)(&DAT_00163c28 + (uint)(byte)(&DAT_00164381)[iVar1] * 4) == 1) ||
        (*(int *)(&DAT_00163c28 + (uint)(byte)(&DAT_00164381)[iVar1] * 4) == 3)) ||
       (param_1 == 0x5f)) {
      uVar2 = 1;
    }
    else {
      uVar2 = 0;
    }
    bVar3 = uVar2 == param_4;
    break;
  default:
    bVar3 = false;
  }
  return bVar3;
}



// ----- 000779e0 : queried -----
// function: FUN_00077988 @ 00077988

undefined1 * FUN_00077988(undefined1 *param_1,int param_2,int param_3)

{
  *param_1 = 0x53;
  param_1[1] = 0xff;
  param_1[2] = (char)((uint)(param_2 - *(int *)(param_3 + 0x18)) >> 8);
  param_1[3] = (char)param_2 - (char)*(undefined4 *)(param_3 + 0x18);
  param_1[4] = 0;
  param_1[5] = 0;
  return param_1 + 6;
}



// ----- 00077924 : queried -----
// function: FUN_000777e4 @ 000777e4

void FUN_000777e4(uint param_1,int param_2,undefined4 param_3,int param_4,undefined1 *param_5)

{
  int iVar1;
  uint uVar2;
  uint local_14;
  undefined1 *local_c;
  
  local_14 = param_1;
  do {
    iVar1 = FUN_00076aec(local_14,param_3);
    if (iVar1 == 0) {
      return;
    }
    for (local_c = param_5; local_c < *(undefined1 **)(param_4 + 0x24); local_c = local_c + 2) {
      uVar2 = (uint)CONCAT11(*local_c,local_c[1]);
      if (*(int *)(param_4 + 0x14) + uVar2 == iVar1 + 1) {
        *local_c = (char)(uVar2 + param_2 >> 8);
        local_c[1] = local_c[1] + (char)param_2;
        break;
      }
    }
    if (*(undefined1 **)(param_4 + 0x24) <= local_c) {
      uVar2 = (uint)CONCAT11(*(undefined1 *)(iVar1 + 1),*(char *)(iVar1 + 2));
      if (param_1 <= *(int *)(param_4 + 0x14) + uVar2) {
        *(char *)(iVar1 + 1) = (char)(uVar2 + param_2 >> 8);
        *(char *)(iVar1 + 2) = *(char *)(iVar1 + 2) + (char)param_2;
      }
    }
    local_14 = iVar1 + 3;
  } while( true );
}



// ----- 00057c58 : queried -----
// function: FUN_00057bf4 @ 00057bf4

/* WARNING: Removing unreachable block (ram,0x00058154) */
/* WARNING: Removing unreachable block (ram,0x0005829c) */

int * FUN_00057bf4(undefined4 *param_1,int *param_2)

{
  ulonglong uVar1;
  ulonglong uVar2;
  longlong lVar3;
  longlong lVar4;
  undefined4 *puVar5;
  int iVar6;
  int iVar7;
  int extraout_r2;
  int extraout_r2_00;
  int extraout_r2_01;
  int extraout_r2_02;
  int extraout_r2_03;
  int extraout_r2_04;
  int extraout_r2_05;
  int extraout_r2_06;
  int extraout_r2_07;
  int extraout_r2_08;
  int extraout_r2_09;
  int extraout_r2_10;
  int extraout_r3;
  int extraout_r3_00;
  int extraout_r3_01;
  int extraout_r3_02;
  int extraout_r3_03;
  int extraout_r3_04;
  int extraout_r3_05;
  int extraout_r3_06;
  undefined4 uVar8;
  uint uVar9;
  undefined4 uVar10;
  int iVar11;
  int iVar12;
  uint uVar13;
  uint *puVar14;
  uint uVar15;
  uint uVar16;
  undefined8 uVar17;
  longlong lVar18;
  uint local_48;
  int iStack_44;
  int local_40;
  int local_3c;
  int local_38;
  int local_34;
  undefined4 local_30;
  
  uVar8 = *param_1;
  uVar10 = param_1[1];
  param_2[8] = 0;
  __aeabi_ldivmod(uVar8,uVar10,0x3c,0);
  uVar17 = __aeabi_ldivmod(uVar8,uVar10,0x3c,0);
  uVar8 = (undefined4)((ulonglong)uVar17 >> 0x20);
  __aeabi_ldivmod((int)uVar17,uVar8,0x3c,0);
  uVar17 = __aeabi_ldivmod((int)uVar17,uVar8,0x3c,0);
  uVar8 = (undefined4)((ulonglong)uVar17 >> 0x20);
  __aeabi_ldivmod((int)uVar17,uVar8,0x18,0);
  lVar18 = __aeabi_ldivmod((int)uVar17,uVar8,0x18,0);
  local_3c = extraout_r2_00;
  local_38 = extraout_r2;
  if (extraout_r2 < 0) {
    local_3c = extraout_r2_00 + -1;
    local_38 = extraout_r2 + 0x3c;
  }
  local_40 = extraout_r2_01;
  if (local_3c < 0) {
    local_3c = local_3c + 0x3c;
    local_40 = extraout_r2_01 + -1;
  }
  if (local_40 < 0) {
    lVar18 = lVar18 + -1;
    local_40 = local_40 + 0x18;
  }
  __aeabi_ldivmod((int)(lVar18 + 4),(int)((ulonglong)(lVar18 + 4) >> 0x20),7,0);
  local_34 = extraout_r2_02;
  if (extraout_r2_02 < 0) {
    local_34 = extraout_r2_02 + 7;
  }
  if (lVar18 < 0x3637) {
    if (-1 < lVar18) {
      uVar13 = 0x7b2;
      local_48 = 0x46;
      goto LAB_00057d2c;
    }
    iVar6 = __aeabi_ldivmod((int)lVar18,(int)((ulonglong)lVar18 >> 0x20),0x23ab1,0);
    uVar13 = iVar6 + 1;
    if (uVar13 == 0) {
      local_48 = 0x45;
      iStack_44 = 0;
      uVar13 = 0;
    }
    else {
      uVar16 = (uint)((ulonglong)uVar13 * 400);
      local_48 = uVar16 + 0x45;
      local_30 = (undefined4)((ulonglong)uVar13 * 0xfffdc54f);
      iStack_44 = ((int)uVar13 >> 0x1f) * 400 + (int)((ulonglong)uVar13 * 400 >> 0x20) +
                  (uint)(0xffffffba < uVar16);
      uVar16 = uVar16 + 0x7b1;
      iVar6 = iStack_44 + (uint)(0xfffff893 < local_48);
      lVar18 = lVar18 + CONCAT44((((int)uVar13 >> 0x1f) * -0x23ab1 - uVar13) +
                                 (int)((ulonglong)uVar13 * 0xfffdc54f >> 0x20),local_30);
      __aeabi_ldivmod(uVar16,iVar6,400,0);
      if ((extraout_r2_07 == 0 && extraout_r3_03 == 0) ||
         (((uVar16 & 3) == 0 &&
          (__aeabi_ldivmod(uVar16,iVar6,100,0), extraout_r2_10 != 0 || extraout_r3_06 != 0)))) {
        uVar13 = 1;
      }
      else {
        uVar13 = 0;
      }
    }
    iVar11 = (int)((ulonglong)lVar18 >> 0x20);
    uVar16 = (&DAT_0016251c)[uVar13];
    iVar6 = (int)-uVar16 >> 0x1f;
    if ((iVar6 != iVar11 && iVar11 <= iVar6) ||
       ((iVar6 == iVar11 && ((uint)lVar18 <= -uVar16 && -(uint)lVar18 != uVar16)))) {
      iStack_44 = iStack_44 + (uint)(0xfffff894 < local_48);
      uVar9 = local_48 + 0x76b;
      do {
        local_48 = uVar9;
        uVar15 = (uint)lVar18 + uVar16;
        iVar6 = (int)((ulonglong)lVar18 >> 0x20) + ((int)uVar16 >> 0x1f) +
                (uint)CARRY4((uint)lVar18,uVar16);
        lVar18 = lVar18 + (int)uVar16;
        __aeabi_ldivmod(local_48,iStack_44,400,0);
        uVar13 = 1;
        if ((extraout_r2_08 != 0 || extraout_r3_04 != 0) && (uVar13 = 0, (local_48 & 3) == 0)) {
          __aeabi_ldivmod(local_48,iStack_44,100,0);
          if (extraout_r2_09 == 0 && extraout_r3_05 == 0) {
            uVar13 = 0;
          }
          else {
            uVar13 = 1;
          }
        }
        uVar16 = (&DAT_0016251c)[uVar13];
        uVar9 = local_48 - 1;
        iStack_44 = iStack_44 + -1 + (uint)(local_48 != 0);
        iVar11 = (int)-uVar16 >> 0x1f;
      } while ((iVar6 < iVar11) || ((iVar11 == iVar6 && (uVar15 <= -uVar16 && -uVar15 != uVar16))));
      local_48 = local_48 - 0x76c;
      iStack_44 = iStack_44 + -1 + (uint)(0x76a < uVar9);
    }
    iVar7 = (int)((ulonglong)lVar18 >> 0x20);
    uVar9 = (uint)lVar18;
    uVar1 = CONCAT44(iStack_44,local_48);
    iVar6 = uVar13 * 2;
    uVar16 = (&DAT_001625b0)[uVar13 * 0xc];
    iVar11 = (int)-uVar16 >> 0x1f;
    if ((iVar11 != iVar7 && iVar7 <= iVar11) ||
       ((iVar11 == iVar7 && (uVar9 <= -uVar16 && -uVar9 != uVar16)))) {
      puVar14 = &DAT_001625b0 + uVar13 * 0xc;
      iVar7 = 0xb;
      do {
        do {
          uVar9 = (uint)lVar18 + uVar16;
          lVar4 = (longlong)(int)uVar16;
          iVar12 = (int)((ulonglong)lVar18 >> 0x20) + ((int)uVar16 >> 0x1f) +
                   (uint)CARRY4((uint)lVar18,uVar16);
          lVar3 = lVar18 + (int)uVar16;
          puVar14 = puVar14 + -1;
          uVar16 = *puVar14;
          iVar7 = iVar7 + -1;
          iVar11 = (int)-uVar16 >> 0x1f;
          lVar18 = lVar18 + lVar4;
        } while (iVar12 < iVar11);
      } while ((iVar11 == iVar12) && (lVar18 = lVar3, uVar9 <= -uVar16 && -uVar9 != uVar16));
    }
    else {
      iVar7 = 0xb;
    }
    uVar9 = uVar9 + uVar16;
  }
  else {
    lVar18 = lVar18 + -0x3637;
    uVar13 = 0x7d8;
    local_48 = 0x6c;
LAB_00057d2c:
    uVar1 = (ulonglong)local_48;
    uVar2 = (ulonglong)uVar13;
    uVar13 = __aeabi_ldivmod((int)lVar18,(int)((ulonglong)lVar18 >> 0x20),0x23ab1,0);
    if (uVar13 == 0) {
LAB_00057f20:
      if (((uVar2 & 3) == 0) &&
         (__aeabi_ldivmod((int)uVar2,(int)(uVar2 >> 0x20),100,0),
         extraout_r2_06 != 0 || extraout_r3_02 != 0)) goto LAB_00057db8;
      uVar13 = 0;
    }
    else {
      uVar1 = (ulonglong)uVar13 * 400 + CONCAT44(((int)uVar13 >> 0x1f) * 400,local_48);
      uVar2 = uVar1 + 0x76c;
      lVar18 = lVar18 + CONCAT44((((int)uVar13 >> 0x1f) * -0x23ab1 - uVar13) +
                                 (int)((ulonglong)uVar13 * 0xfffdc54f >> 0x20),
                                 (int)((ulonglong)uVar13 * 0xfffdc54f));
      __aeabi_ldivmod((int)uVar2,(int)(uVar2 >> 0x20),400,0);
      if (extraout_r2_03 != 0 || extraout_r3 != 0) goto LAB_00057f20;
LAB_00057db8:
      uVar13 = 1;
    }
    uVar16 = (&DAT_0016251c)[uVar13];
    iVar6 = (int)uVar16 >> 0x1f;
    if ((int)uVar16 <= lVar18) {
      uVar1 = uVar1 + 0x76d;
      do {
        iVar7 = (int)(uVar1 >> 0x20);
        uVar15 = (uint)uVar1;
        __aeabi_ldivmod(uVar15,iVar7,400,0);
        uVar9 = (uint)lVar18 - uVar16;
        iVar11 = (int)((ulonglong)lVar18 >> 0x20) - (iVar6 + (uint)((uint)lVar18 < uVar16));
        lVar18 = CONCAT44(iVar11,uVar9);
        uVar13 = 1;
        if (((extraout_r2_04 != 0 || extraout_r3_00 != 0) && (uVar13 = 0, (uVar1 & 3) == 0)) &&
           (__aeabi_ldivmod(uVar15,iVar7,100,0), uVar13 = uVar15 & 3,
           extraout_r2_05 != 0 || extraout_r3_01 != 0)) {
          uVar13 = 1;
        }
        uVar16 = (&DAT_0016251c)[uVar13];
        iVar6 = (int)uVar16 >> 0x1f;
        uVar2 = uVar1 + 1;
      } while ((iVar6 <= iVar11) &&
              ((uVar1 = uVar1 + 1, iVar6 != iVar11 || (uVar1 = uVar2, uVar16 <= uVar9))));
      uVar1 = CONCAT44(iVar7 + (uint)(0xfffffffe < uVar15) + -1 + (uint)(0x76c < uVar15 + 1),
                       uVar15 - 0x76c);
    }
    iVar7 = (int)((ulonglong)lVar18 >> 0x20);
    uVar9 = (uint)lVar18;
    iStack_44 = (int)(uVar1 >> 0x20);
    local_48 = (uint)uVar1;
    iVar6 = uVar13 * 2;
    uVar16 = *(uint *)(&UNK_00162584 + uVar13 * 0x30);
    iVar11 = (int)uVar16 >> 0x1f;
    if ((iVar11 == iVar7 || iVar11 < iVar7) && ((iVar11 != iVar7 || (uVar16 <= uVar9)))) {
      puVar14 = (uint *)(&UNK_00162584 + uVar13 * 0x30);
      iVar7 = 0;
      do {
        puVar14 = puVar14 + 1;
        uVar15 = *puVar14;
        uVar9 = (uint)lVar18 - uVar16;
        iVar12 = (int)((ulonglong)lVar18 >> 0x20) - (iVar11 + (uint)((uint)lVar18 < uVar16));
        iVar11 = (int)uVar15 >> 0x1f;
        iVar7 = iVar7 + 1;
        if (iVar12 < iVar11) goto LAB_00057eec;
        uVar16 = uVar15;
        lVar18 = CONCAT44(iVar12,uVar9);
      } while ((iVar11 != iVar12) || (lVar18 = CONCAT44(iVar12,uVar9), uVar15 <= uVar9));
      param_2[5] = local_48;
      if ((int)local_48 >> 0x1f == iStack_44) goto LAB_00057f80;
      goto LAB_00057f04;
    }
    iVar7 = 0;
  }
LAB_00057eec:
  iStack_44 = (int)(uVar1 >> 0x20);
  local_48 = (uint)uVar1;
  param_2[5] = local_48;
  if ((int)local_48 >> 0x1f == iStack_44) {
LAB_00057f80:
    param_2[7] = (&DAT_00162524)[iVar7 + (iVar6 + uVar13) * 4] + uVar9;
    param_2[3] = uVar9 + 1;
    *param_2 = local_38;
    param_2[1] = local_3c;
    param_2[2] = local_40;
    param_2[4] = iVar7;
    param_2[6] = local_34;
    return param_2;
  }
LAB_00057f04:
  puVar5 = (undefined4 *)__errno();
  *puVar5 = 0x4b;
  return (int *)0x0;
}



// ----- 0005794c : queried -----
// function: FUN_00057840 @ 00057840

undefined8 FUN_00057840(uint *param_1)

{
  longlong lVar1;
  ulonglong uVar2;
  longlong lVar3;
  int iVar4;
  int extraout_r2;
  int extraout_r2_00;
  int extraout_r2_01;
  uint uVar5;
  int extraout_r2_02;
  int extraout_r2_03;
  int extraout_r2_04;
  int extraout_r3;
  int extraout_r3_00;
  uint uVar6;
  int extraout_r3_01;
  int extraout_r3_02;
  int extraout_r3_03;
  int extraout_r3_04;
  uint uVar7;
  uint uVar8;
  int iVar9;
  int iVar10;
  int iVar11;
  uint uVar12;
  bool bVar13;
  uint local_38;
  int local_34;
  
  local_38 = param_1[5];
  local_34 = (int)local_38 >> 0x1f;
  if ((-1 >= (int)local_38 && -1 < local_34) || ((-1 < (int)local_38 && (100 < local_38)))) {
    iVar4 = __aeabi_ldivmod(local_38 - 100,local_34 + -1 + (uint)(99 < local_38),400,0);
    bVar13 = local_38 < (uint)(iVar4 * 400);
    local_38 = local_38 + iVar4 * -400;
    local_34 = local_34 - ((iVar4 * 400 >> 0x1f) + (uint)bVar13);
    lVar1 = (longlong)iVar4 * 0x23ab1;
  }
  else if ((local_34 < -1) || (((int)local_38 < 0 && (local_38 < 0xfffffed4)))) {
    iVar4 = __aeabi_ldivmod(local_38 - 100,local_34 + -1 + (uint)(99 < local_38),400,0);
    lVar1 = (longlong)iVar4 * 0x23ab1;
    bVar13 = local_38 < (uint)(iVar4 * 400);
    local_38 = local_38 + iVar4 * -400;
    local_34 = local_34 - ((iVar4 * 400 >> 0x1f) + (uint)bVar13);
  }
  else {
    lVar1 = 0;
  }
  if ((local_34 < 1) && ((local_34 != 0 || (local_38 < 0x47)))) {
    if ((local_38 == 0x46) && (local_34 == 0)) {
      iVar4 = 0;
      goto LAB_0005799c;
    }
    iVar4 = 0;
    uVar7 = 0x7b1;
    do {
      __aeabi_ldivmod(uVar7,iVar4,400,0);
      iVar11 = 1;
      if ((extraout_r2_03 != 0 || extraout_r3_03 != 0) && (iVar11 = 0, (uVar7 & 3) == 0)) {
        __aeabi_ldivmod(uVar7,iVar4,100,0);
        if (extraout_r2_04 == 0 && extraout_r3_04 == 0) {
          iVar11 = 0;
        }
        else {
          iVar11 = 1;
        }
      }
      uVar8 = uVar7 - 1;
      iVar4 = iVar4 + -1 + (uint)(uVar7 != 0);
      uVar6 = (&DAT_0016251c)[iVar11];
      uVar5 = uVar7 - 0x76d;
      iVar11 = iVar4 + -1 + (uint)(0x76b < uVar8);
      iVar9 = (uint)lVar1 - uVar6;
      iVar10 = (int)((ulonglong)lVar1 >> 0x20) -
               (((int)uVar6 >> 0x1f) + (uint)((uint)lVar1 < uVar6));
    } while ((local_34 <= iVar11) &&
            ((uVar7 = uVar8, lVar1 = CONCAT44(iVar10,iVar9), local_34 != iVar11 ||
             (lVar1 = CONCAT44(iVar10,iVar9), local_38 <= uVar5))));
  }
  else {
    uVar7 = 0x7b2;
    iVar4 = 0;
    do {
      __aeabi_ldivmod(uVar7,iVar4,400,0);
      iVar11 = 1;
      if ((extraout_r2 != 0 || extraout_r3 != 0) && (iVar11 = 0, (uVar7 & 3) == 0)) {
        __aeabi_ldivmod(uVar7,iVar4,100,0);
        if (extraout_r2_00 == 0 && extraout_r3_00 == 0) {
          iVar11 = 0;
        }
        else {
          iVar11 = 1;
        }
      }
      bVar13 = 0xfffffffe < uVar7;
      uVar7 = uVar7 + 1;
      uVar6 = (&DAT_0016251c)[iVar11];
      iVar4 = iVar4 + (uint)bVar13;
      iVar9 = (uint)lVar1 + uVar6;
      iVar10 = (int)((ulonglong)lVar1 >> 0x20) + ((int)uVar6 >> 0x1f) +
               (uint)CARRY4((uint)lVar1,uVar6);
      lVar3 = lVar1 + (int)uVar6;
      lVar1 = lVar1 + (int)uVar6;
    } while ((uVar7 != local_38 + 0x76c) ||
            (lVar1 = lVar3, iVar4 != local_34 + (uint)(0xfffff893 < local_38)));
  }
  lVar1 = CONCAT44(iVar10,iVar9);
  uVar7 = local_38 + 0x76c;
  local_34 = local_34 + (uint)(0xfffff893 < local_38);
  __aeabi_ldivmod(uVar7,local_34,400,0);
  if ((extraout_r2_01 == 0 && extraout_r3_01 == 0) ||
     (((uVar7 & 3) == 0 &&
      (__aeabi_ldivmod(uVar7,local_34,100,0), extraout_r2_02 != 0 || extraout_r3_02 != 0)))) {
    iVar4 = 1;
    lVar1 = CONCAT44(iVar10,iVar9);
  }
  else {
    iVar4 = 0;
  }
LAB_0005799c:
  uVar7 = (&DAT_00162524)[param_1[4] + iVar4 * 0xc];
  uVar6 = param_1[3] - 1;
  uVar2 = lVar1 + CONCAT44(((int)uVar7 >> 0x1f) + ((int)uVar6 >> 0x1f) + (uint)CARRY4(uVar7,uVar6),
                           uVar7 + uVar6);
  lVar1 = (uVar2 & 0xffffffff) * 0x15180;
  uVar6 = (uint)lVar1;
  uVar8 = param_1[2] * 0xe10;
  uVar7 = param_1[1] * 0x3c;
  uVar12 = *param_1;
  uVar5 = uVar7 + uVar8 + uVar12;
  return CONCAT44(((int)uVar7 >> 0x1f) + ((int)uVar8 >> 0x1f) + (uint)CARRY4(uVar7,uVar8) +
                  ((int)uVar12 >> 0x1f) + (uint)CARRY4(uVar7 + uVar8,uVar12) +
                  (int)(uVar2 >> 0x20) * 0x15180 + (int)((ulonglong)lVar1 >> 0x20) +
                  (uint)CARRY4(uVar5,uVar6),uVar5 + uVar6);
}



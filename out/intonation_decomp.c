
// ----- 00066230 : queried -----
// function: FUN_00066230 @ 00066230

undefined4 FUN_00066230(undefined4 param_1)

{
  undefined4 uVar1;
  int iVar2;
  undefined4 uVar3;
  
  uVar1 = FUN_0005978c(param_1,&DAT_0015926c);
  FUN_00059720(param_1,"Token");
  for (iVar2 = FUN_000595f8(); iVar2 != 0; iVar2 = FUN_00058e40(iVar2)) {
    FUN_00058fec(iVar2,&DAT_00155d00);
    uVar3 = FUN_00070040();
    FUN_00058fcc(iVar2,"phones",uVar3);
    uVar3 = FUN_00059544(iVar2,0);
    FUN_00058f6c(uVar3,&DAT_00155d00,&DAT_001549d3);
    FUN_00059660(uVar1,uVar3);
  }
  return param_1;
}



// ----- 00066554 : queried -----
// function: FUN_00066554 @ 00066554

undefined4 * FUN_00066554(undefined4 *param_1)

{
  int iVar1;
  int iVar2;
  char *pcVar3;
  int iVar4;
  int iVar5;
  int iVar6;
  code *pcVar7;
  
  iVar1 = FUN_0005b10c(*param_1,"phrasesylendtone_func");
  FUN_00059720(param_1,"Phrase");
  iVar2 = FUN_000595f8();
  do {
    while( true ) {
      if (iVar2 == 0) {
        return param_1;
      }
      iVar5 = FUN_00062124(iVar2,"daughtern.R:SylStructure.daughtern");
      if (iVar5 != 0) break;
LAB_0006660c:
      iVar2 = FUN_00058e40(iVar2);
    }
    iVar6 = FUN_00061d28(iVar2,"daughtern.R:Token.parent.endtone");
    if (iVar6 != 0) {
      pcVar3 = (char *)FUN_0005cfc0();
      iVar4 = strcmp(pcVar3,"H");
      if (iVar4 != 0) {
        pcVar3 = (char *)FUN_0005cfc0(iVar6);
        iVar4 = strcmp(pcVar3,"L");
        if (iVar4 != 0) goto LAB_00066644;
      }
      FUN_00058fcc(iVar5,"endtone",iVar6);
      goto LAB_0006660c;
    }
LAB_00066644:
    if (iVar1 == 0) {
LAB_0006668c:
      FUN_00058f6c(iVar5,"endtone",&DAT_0015737c);
      goto LAB_0006660c;
    }
    pcVar7 = (code *)FUN_0005922c();
    iVar6 = (*pcVar7)(iVar2);
    if (iVar6 == 0) goto LAB_0006668c;
    FUN_00058fcc(iVar5,"endtone");
    iVar2 = FUN_00058e40(iVar2);
  } while( true );
}



// ----- 000666c8 : queried -----
// function: FUN_000666c8 @ 000666c8

undefined4 * FUN_000666c8(undefined4 *param_1)

{
  undefined4 uVar1;
  int iVar2;
  undefined4 uVar3;
  int iVar4;
  int iVar5;
  
  FUN_0005b10c(*param_1,"silence");
  uVar1 = FUN_0005cfc0();
  FUN_00059720(param_1,"Segment");
  iVar2 = FUN_000595f8();
  if (iVar2 == 0) {
    uVar3 = FUN_00059720(param_1,"Segment");
    uVar3 = FUN_00059660(uVar3,0);
  }
  else {
    uVar3 = FUN_0005946c(iVar2,0);
  }
  FUN_00058f6c(uVar3,&DAT_00155d00,uVar1);
  FUN_00059720(param_1,"Phrase");
  iVar2 = FUN_000595f8();
  do {
    if (iVar2 == 0) {
      return param_1;
    }
    for (iVar4 = FUN_00058ecc(iVar2); iVar4 != 0; iVar4 = FUN_00058e4c(iVar4)) {
      iVar5 = FUN_00062124(iVar4,"R:SylStructure.daughtern.daughtern.R:Segment");
      if (iVar5 != 0) {
        uVar3 = FUN_000594e4(iVar5,0);
        FUN_00058f6c(uVar3,&DAT_00155d00,uVar1);
        break;
      }
    }
    iVar2 = FUN_00058e40(iVar2);
  } while( true );
}



// ----- 000667e0 : queried -----
// function: FUN_000667e0 @ 000667e0

undefined4 * FUN_000667e0(undefined4 *param_1)

{
  undefined4 uVar1;
  undefined4 uVar2;
  undefined4 uVar3;
  int iVar4;
  int iVar5;
  int iVar6;
  undefined4 uVar7;
  undefined4 uVar8;
  int iVar9;
  undefined4 *puVar10;
  int iVar11;
  code *pcVar12;
  char *__s2;
  int iVar13;
  size_t sVar14;
  char *pcVar15;
  undefined4 uVar16;
  uint uVar17;
  uint __c;
  int iStack_88;
  int iStack_84;
  int iStack_80;
  uint uStack_74;
  int iStack_70;
  
  uVar1 = FUN_0005978c(param_1,"SylStructure");
  uVar2 = FUN_0005978c(param_1,"Syllable");
  uVar3 = FUN_0005978c(param_1,"Segment");
  iVar4 = FUN_0005b10c(*param_1,"user_lexicon");
  iVar5 = FUN_0005b10c(*param_1,"vox_lexicon");
  iVar6 = FUN_0005b10c(*param_1,"wordtosegments_func");
  FUN_00059720(param_1,&DAT_0015926c);
  iStack_70 = FUN_000595f8();
  if (iStack_70 != 0) {
    do {
      uVar7 = FUN_00059660(uVar1,iStack_70);
      FUN_00059334(iStack_70,"Token");
      uVar8 = FUN_00058e58();
      iVar9 = FUN_00059034(uVar8,"xsampa");
      if (iVar9 == 0) {
LAB_00066b6c:
        FUN_00059334(iStack_70,"Token");
        uVar8 = FUN_00058e58();
        iVar9 = FUN_00059034(uVar8,"phones");
        if ((iVar9 == 0) && (iVar9 = FUN_00059034(iStack_70,"phones"), iVar9 == 0)) {
          uStack_74 = 0;
          goto LAB_00066968;
        }
        iVar11 = FUN_0005cd54(iVar9);
        if (iVar11 == 0) {
          FUN_0005cfc0(iVar9);
          uStack_74 = FUN_00070040();
        }
        else {
          uVar8 = 0;
          do {
            uVar16 = FUN_0005cf98(iVar9);
            uVar8 = FUN_0005d5d0(uVar16,uVar8);
            iVar9 = FUN_0005cedc(iVar9);
          } while (iVar9 != 0);
          uStack_74 = FUN_0005cd64(uVar8);
        }
        iVar9 = FUN_0005d040(&DAT_00155174,uStack_74);
        if (iVar9 != 0) goto LAB_00066968;
        puVar10 = (undefined4 *)FUN_00058f0c(iStack_70);
        iVar9 = FUN_0005b10c(*puVar10,"syl_boundaries_func");
        if (iVar9 == 0) {
          uVar8 = FUN_0006f848(iStack_70);
          uStack_74 = FUN_0006f374(uVar8,uStack_74);
          goto LAB_00066968;
        }
        pcVar12 = (code *)FUN_000700f8();
        uStack_74 = (*pcVar12)(uStack_74);
        uVar17 = 1 - uStack_74;
        if (1 < uStack_74) {
          uVar17 = 0;
        }
      }
      else {
        puVar10 = (undefined4 *)FUN_00058f0c(iStack_70);
        iVar11 = FUN_0005b10c(*puVar10,"xsampa_to_xivona_func");
        if (iVar11 == 0) goto LAB_00066b6c;
        pcVar12 = (code *)FUN_000653bc();
        FUN_0005cfc0(iVar9);
        uStack_74 = (*pcVar12)();
LAB_00066968:
        uVar17 = 1 - uStack_74;
        if (1 < uStack_74) {
          uVar17 = 0;
        }
      }
      if ((uVar17 & iVar4 != 0) != 0) {
        uVar8 = FUN_00058fec(iStack_70,&DAT_00155d00);
        iVar9 = FUN_00065138(iVar4,uVar8,0);
        if (iVar9 == 0) {
          uVar17 = 1;
        }
        else {
          for (iVar9 = FUN_0005cedc(); iVar9 != 0; iVar9 = FUN_0005cedc(iVar9)) {
            uVar8 = FUN_0005cf98(iVar9);
            uStack_74 = FUN_0005d5d0(uVar8,uStack_74);
          }
          uStack_74 = FUN_0005cd64(uStack_74);
          uVar17 = 1 - uStack_74;
          if (1 < uStack_74) {
            uVar17 = 0;
          }
        }
      }
      if ((uVar17 & iVar5 != 0) != 0) {
        uVar8 = FUN_00068fec(iVar5);
        uVar16 = FUN_00058fec(iStack_70,&DAT_00155d00);
        uStack_74 = FUN_00069044(uVar8,uVar16,0);
        uVar17 = 1 - uStack_74;
        if (1 < uStack_74) {
          uVar17 = 0;
        }
      }
      if ((uVar17 & iVar6 != 0) != 0) {
        pcVar12 = (code *)FUN_0005922c(iVar6);
        uStack_74 = (*pcVar12)(iStack_70);
      }
      if (uStack_74 != 0) {
        iStack_84 = 0;
        iVar9 = 0;
        iStack_80 = 0;
        iStack_88 = 0;
        uVar17 = uStack_74;
        iVar11 = 0;
        do {
          while( true ) {
            FUN_0005cf98(uVar17);
            FUN_0005cfc0();
            __s2 = (char *)FUN_0005b884();
            if (iStack_80 == 0) {
              iStack_80 = FUN_00059660(uVar2,0);
              iVar9 = 0;
              iStack_88 = FUN_00059544(uVar7,iStack_80);
            }
            iVar13 = strcmp("-",__s2);
            if (iVar13 != 0) break;
            iStack_84 = 0;
LAB_000669d8:
            if (iStack_88 == 0) {
              iStack_80 = iStack_88;
            }
            else {
              FUN_00058fac(iStack_88,"glottal_stop_pos",iVar11);
              FUN_00058fac(iStack_88,"stress",iVar9);
              iStack_80 = 0;
            }
            FUN_0005ac04(__s2);
            uVar17 = FUN_0005cedc(uVar17);
            iVar11 = iStack_80;
            if (uVar17 == 0) goto LAB_00066b1c;
          }
          iStack_84 = iStack_84 + 1;
          uVar8 = FUN_00059660(uVar3,0);
          while( true ) {
            sVar14 = strlen(__s2);
            __c = (uint)(byte)__s2[sVar14 - 1];
            pcVar15 = strchr("0123?",__c);
            if (pcVar15 == (char *)0x0) break;
            iVar13 = iStack_84;
            if (__c != 0x3f) {
              iVar9 = __c - 0x30;
              iVar13 = iVar11;
            }
            __s2[sVar14 - 1] = '\0';
            iVar11 = iVar13;
          }
          FUN_00058f6c(uVar8,&DAT_00155d00,__s2);
          FUN_00059544(iStack_88,uVar8);
          iVar13 = strcmp("-",__s2);
          if ((iVar13 == 0) || (iVar13 = FUN_0005cedc(uVar17), iVar13 == 0)) goto LAB_000669d8;
          FUN_0005ac04(__s2);
          uVar17 = FUN_0005cedc(uVar17);
        } while (uVar17 != 0);
      }
LAB_00066b1c:
      FUN_0005d4fc(uStack_74);
      iStack_70 = FUN_00058e40(iStack_70);
    } while (iStack_70 != 0);
  }
  return param_1;
}



// ----- 00066830 : queried -----
// function: FUN_000667e0 @ 000667e0

undefined4 * FUN_000667e0(undefined4 *param_1)

{
  undefined4 uVar1;
  undefined4 uVar2;
  undefined4 uVar3;
  int iVar4;
  int iVar5;
  int iVar6;
  undefined4 uVar7;
  undefined4 uVar8;
  int iVar9;
  undefined4 *puVar10;
  int iVar11;
  code *pcVar12;
  char *__s2;
  int iVar13;
  size_t sVar14;
  char *pcVar15;
  undefined4 uVar16;
  uint uVar17;
  uint __c;
  int iStack_88;
  int iStack_84;
  int iStack_80;
  uint uStack_74;
  int iStack_70;
  
  uVar1 = FUN_0005978c(param_1,"SylStructure");
  uVar2 = FUN_0005978c(param_1,"Syllable");
  uVar3 = FUN_0005978c(param_1,"Segment");
  iVar4 = FUN_0005b10c(*param_1,"user_lexicon");
  iVar5 = FUN_0005b10c(*param_1,"vox_lexicon");
  iVar6 = FUN_0005b10c(*param_1,"wordtosegments_func");
  FUN_00059720(param_1,&DAT_0015926c);
  iStack_70 = FUN_000595f8();
  if (iStack_70 != 0) {
    do {
      uVar7 = FUN_00059660(uVar1,iStack_70);
      FUN_00059334(iStack_70,"Token");
      uVar8 = FUN_00058e58();
      iVar9 = FUN_00059034(uVar8,"xsampa");
      if (iVar9 == 0) {
LAB_00066b6c:
        FUN_00059334(iStack_70,"Token");
        uVar8 = FUN_00058e58();
        iVar9 = FUN_00059034(uVar8,"phones");
        if ((iVar9 == 0) && (iVar9 = FUN_00059034(iStack_70,"phones"), iVar9 == 0)) {
          uStack_74 = 0;
          goto LAB_00066968;
        }
        iVar11 = FUN_0005cd54(iVar9);
        if (iVar11 == 0) {
          FUN_0005cfc0(iVar9);
          uStack_74 = FUN_00070040();
        }
        else {
          uVar8 = 0;
          do {
            uVar16 = FUN_0005cf98(iVar9);
            uVar8 = FUN_0005d5d0(uVar16,uVar8);
            iVar9 = FUN_0005cedc(iVar9);
          } while (iVar9 != 0);
          uStack_74 = FUN_0005cd64(uVar8);
        }
        iVar9 = FUN_0005d040(&DAT_00155174,uStack_74);
        if (iVar9 != 0) goto LAB_00066968;
        puVar10 = (undefined4 *)FUN_00058f0c(iStack_70);
        iVar9 = FUN_0005b10c(*puVar10,"syl_boundaries_func");
        if (iVar9 == 0) {
          uVar8 = FUN_0006f848(iStack_70);
          uStack_74 = FUN_0006f374(uVar8,uStack_74);
          goto LAB_00066968;
        }
        pcVar12 = (code *)FUN_000700f8();
        uStack_74 = (*pcVar12)(uStack_74);
        uVar17 = 1 - uStack_74;
        if (1 < uStack_74) {
          uVar17 = 0;
        }
      }
      else {
        puVar10 = (undefined4 *)FUN_00058f0c(iStack_70);
        iVar11 = FUN_0005b10c(*puVar10,"xsampa_to_xivona_func");
        if (iVar11 == 0) goto LAB_00066b6c;
        pcVar12 = (code *)FUN_000653bc();
        FUN_0005cfc0(iVar9);
        uStack_74 = (*pcVar12)();
LAB_00066968:
        uVar17 = 1 - uStack_74;
        if (1 < uStack_74) {
          uVar17 = 0;
        }
      }
      if ((uVar17 & iVar4 != 0) != 0) {
        uVar8 = FUN_00058fec(iStack_70,&DAT_00155d00);
        iVar9 = FUN_00065138(iVar4,uVar8,0);
        if (iVar9 == 0) {
          uVar17 = 1;
        }
        else {
          for (iVar9 = FUN_0005cedc(); iVar9 != 0; iVar9 = FUN_0005cedc(iVar9)) {
            uVar8 = FUN_0005cf98(iVar9);
            uStack_74 = FUN_0005d5d0(uVar8,uStack_74);
          }
          uStack_74 = FUN_0005cd64(uStack_74);
          uVar17 = 1 - uStack_74;
          if (1 < uStack_74) {
            uVar17 = 0;
          }
        }
      }
      if ((uVar17 & iVar5 != 0) != 0) {
        uVar8 = FUN_00068fec(iVar5);
        uVar16 = FUN_00058fec(iStack_70,&DAT_00155d00);
        uStack_74 = FUN_00069044(uVar8,uVar16,0);
        uVar17 = 1 - uStack_74;
        if (1 < uStack_74) {
          uVar17 = 0;
        }
      }
      if ((uVar17 & iVar6 != 0) != 0) {
        pcVar12 = (code *)FUN_0005922c(iVar6);
        uStack_74 = (*pcVar12)(iStack_70);
      }
      if (uStack_74 != 0) {
        iStack_84 = 0;
        iVar9 = 0;
        iStack_80 = 0;
        iStack_88 = 0;
        uVar17 = uStack_74;
        iVar11 = 0;
        do {
          while( true ) {
            FUN_0005cf98(uVar17);
            FUN_0005cfc0();
            __s2 = (char *)FUN_0005b884();
            if (iStack_80 == 0) {
              iStack_80 = FUN_00059660(uVar2,0);
              iVar9 = 0;
              iStack_88 = FUN_00059544(uVar7,iStack_80);
            }
            iVar13 = strcmp("-",__s2);
            if (iVar13 != 0) break;
            iStack_84 = 0;
LAB_000669d8:
            if (iStack_88 == 0) {
              iStack_80 = iStack_88;
            }
            else {
              FUN_00058fac(iStack_88,"glottal_stop_pos",iVar11);
              FUN_00058fac(iStack_88,"stress",iVar9);
              iStack_80 = 0;
            }
            FUN_0005ac04(__s2);
            uVar17 = FUN_0005cedc(uVar17);
            iVar11 = iStack_80;
            if (uVar17 == 0) goto LAB_00066b1c;
          }
          iStack_84 = iStack_84 + 1;
          uVar8 = FUN_00059660(uVar3,0);
          while( true ) {
            sVar14 = strlen(__s2);
            __c = (uint)(byte)__s2[sVar14 - 1];
            pcVar15 = strchr("0123?",__c);
            if (pcVar15 == (char *)0x0) break;
            iVar13 = iStack_84;
            if (__c != 0x3f) {
              iVar9 = __c - 0x30;
              iVar13 = iVar11;
            }
            __s2[sVar14 - 1] = '\0';
            iVar11 = iVar13;
          }
          FUN_00058f6c(uVar8,&DAT_00155d00,__s2);
          FUN_00059544(iStack_88,uVar8);
          iVar13 = strcmp("-",__s2);
          if ((iVar13 == 0) || (iVar13 = FUN_0005cedc(uVar17), iVar13 == 0)) goto LAB_000669d8;
          FUN_0005ac04(__s2);
          uVar17 = FUN_0005cedc(uVar17);
        } while (uVar17 != 0);
      }
LAB_00066b1c:
      FUN_0005d4fc(uStack_74);
      iStack_70 = FUN_00058e40(iStack_70);
    } while (iStack_70 != 0);
  }
  return param_1;
}



// ----- 00066900 : queried -----
// function: FUN_000667e0 @ 000667e0

undefined4 * FUN_000667e0(undefined4 *param_1)

{
  undefined4 uVar1;
  undefined4 uVar2;
  undefined4 uVar3;
  int iVar4;
  int iVar5;
  int iVar6;
  undefined4 uVar7;
  undefined4 uVar8;
  int iVar9;
  undefined4 *puVar10;
  int iVar11;
  code *pcVar12;
  char *__s2;
  int iVar13;
  size_t sVar14;
  char *pcVar15;
  undefined4 uVar16;
  uint uVar17;
  uint __c;
  int iStack_88;
  int iStack_84;
  int iStack_80;
  uint uStack_74;
  int iStack_70;
  
  uVar1 = FUN_0005978c(param_1,"SylStructure");
  uVar2 = FUN_0005978c(param_1,"Syllable");
  uVar3 = FUN_0005978c(param_1,"Segment");
  iVar4 = FUN_0005b10c(*param_1,"user_lexicon");
  iVar5 = FUN_0005b10c(*param_1,"vox_lexicon");
  iVar6 = FUN_0005b10c(*param_1,"wordtosegments_func");
  FUN_00059720(param_1,&DAT_0015926c);
  iStack_70 = FUN_000595f8();
  if (iStack_70 != 0) {
    do {
      uVar7 = FUN_00059660(uVar1,iStack_70);
      FUN_00059334(iStack_70,"Token");
      uVar8 = FUN_00058e58();
      iVar9 = FUN_00059034(uVar8,"xsampa");
      if (iVar9 == 0) {
LAB_00066b6c:
        FUN_00059334(iStack_70,"Token");
        uVar8 = FUN_00058e58();
        iVar9 = FUN_00059034(uVar8,"phones");
        if ((iVar9 == 0) && (iVar9 = FUN_00059034(iStack_70,"phones"), iVar9 == 0)) {
          uStack_74 = 0;
          goto LAB_00066968;
        }
        iVar11 = FUN_0005cd54(iVar9);
        if (iVar11 == 0) {
          FUN_0005cfc0(iVar9);
          uStack_74 = FUN_00070040();
        }
        else {
          uVar8 = 0;
          do {
            uVar16 = FUN_0005cf98(iVar9);
            uVar8 = FUN_0005d5d0(uVar16,uVar8);
            iVar9 = FUN_0005cedc(iVar9);
          } while (iVar9 != 0);
          uStack_74 = FUN_0005cd64(uVar8);
        }
        iVar9 = FUN_0005d040(&DAT_00155174,uStack_74);
        if (iVar9 != 0) goto LAB_00066968;
        puVar10 = (undefined4 *)FUN_00058f0c(iStack_70);
        iVar9 = FUN_0005b10c(*puVar10,"syl_boundaries_func");
        if (iVar9 == 0) {
          uVar8 = FUN_0006f848(iStack_70);
          uStack_74 = FUN_0006f374(uVar8,uStack_74);
          goto LAB_00066968;
        }
        pcVar12 = (code *)FUN_000700f8();
        uStack_74 = (*pcVar12)(uStack_74);
        uVar17 = 1 - uStack_74;
        if (1 < uStack_74) {
          uVar17 = 0;
        }
      }
      else {
        puVar10 = (undefined4 *)FUN_00058f0c(iStack_70);
        iVar11 = FUN_0005b10c(*puVar10,"xsampa_to_xivona_func");
        if (iVar11 == 0) goto LAB_00066b6c;
        pcVar12 = (code *)FUN_000653bc();
        FUN_0005cfc0(iVar9);
        uStack_74 = (*pcVar12)();
LAB_00066968:
        uVar17 = 1 - uStack_74;
        if (1 < uStack_74) {
          uVar17 = 0;
        }
      }
      if ((uVar17 & iVar4 != 0) != 0) {
        uVar8 = FUN_00058fec(iStack_70,&DAT_00155d00);
        iVar9 = FUN_00065138(iVar4,uVar8,0);
        if (iVar9 == 0) {
          uVar17 = 1;
        }
        else {
          for (iVar9 = FUN_0005cedc(); iVar9 != 0; iVar9 = FUN_0005cedc(iVar9)) {
            uVar8 = FUN_0005cf98(iVar9);
            uStack_74 = FUN_0005d5d0(uVar8,uStack_74);
          }
          uStack_74 = FUN_0005cd64(uStack_74);
          uVar17 = 1 - uStack_74;
          if (1 < uStack_74) {
            uVar17 = 0;
          }
        }
      }
      if ((uVar17 & iVar5 != 0) != 0) {
        uVar8 = FUN_00068fec(iVar5);
        uVar16 = FUN_00058fec(iStack_70,&DAT_00155d00);
        uStack_74 = FUN_00069044(uVar8,uVar16,0);
        uVar17 = 1 - uStack_74;
        if (1 < uStack_74) {
          uVar17 = 0;
        }
      }
      if ((uVar17 & iVar6 != 0) != 0) {
        pcVar12 = (code *)FUN_0005922c(iVar6);
        uStack_74 = (*pcVar12)(iStack_70);
      }
      if (uStack_74 != 0) {
        iStack_84 = 0;
        iVar9 = 0;
        iStack_80 = 0;
        iStack_88 = 0;
        uVar17 = uStack_74;
        iVar11 = 0;
        do {
          while( true ) {
            FUN_0005cf98(uVar17);
            FUN_0005cfc0();
            __s2 = (char *)FUN_0005b884();
            if (iStack_80 == 0) {
              iStack_80 = FUN_00059660(uVar2,0);
              iVar9 = 0;
              iStack_88 = FUN_00059544(uVar7,iStack_80);
            }
            iVar13 = strcmp("-",__s2);
            if (iVar13 != 0) break;
            iStack_84 = 0;
LAB_000669d8:
            if (iStack_88 == 0) {
              iStack_80 = iStack_88;
            }
            else {
              FUN_00058fac(iStack_88,"glottal_stop_pos",iVar11);
              FUN_00058fac(iStack_88,"stress",iVar9);
              iStack_80 = 0;
            }
            FUN_0005ac04(__s2);
            uVar17 = FUN_0005cedc(uVar17);
            iVar11 = iStack_80;
            if (uVar17 == 0) goto LAB_00066b1c;
          }
          iStack_84 = iStack_84 + 1;
          uVar8 = FUN_00059660(uVar3,0);
          while( true ) {
            sVar14 = strlen(__s2);
            __c = (uint)(byte)__s2[sVar14 - 1];
            pcVar15 = strchr("0123?",__c);
            if (pcVar15 == (char *)0x0) break;
            iVar13 = iStack_84;
            if (__c != 0x3f) {
              iVar9 = __c - 0x30;
              iVar13 = iVar11;
            }
            __s2[sVar14 - 1] = '\0';
            iVar11 = iVar13;
          }
          FUN_00058f6c(uVar8,&DAT_00155d00,__s2);
          FUN_00059544(iStack_88,uVar8);
          iVar13 = strcmp("-",__s2);
          if ((iVar13 == 0) || (iVar13 = FUN_0005cedc(uVar17), iVar13 == 0)) goto LAB_000669d8;
          FUN_0005ac04(__s2);
          uVar17 = FUN_0005cedc(uVar17);
        } while (uVar17 != 0);
      }
LAB_00066b1c:
      FUN_0005d4fc(uStack_74);
      iStack_70 = FUN_00058e40(iStack_70);
    } while (iStack_70 != 0);
  }
  return param_1;
}



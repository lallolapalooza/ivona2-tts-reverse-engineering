
// ----- 00032d20 : queried -----
// function: FUN_00032d20 @ 00032d20

void FUN_00032d20(void)

{
  undefined4 uVar1;
  undefined4 *puVar2;
  int unaff_r5;
  int iVar3;
  int unaff_r6;
  undefined4 uVar4;
  
  puVar2 = (undefined4 *)(unaff_r6 >> 0x1a);
  FUN_00027a18();
  FUN_00026a54();
  iVar3 = *(int *)(unaff_r5 + 0x1e4);
  uVar4 = *puVar2;
  uVar1 = FUN_00028fa0(*(undefined4 *)(unaff_r5 + 0x1c8));
  FUN_00026a54(uVar4,"wordtosegments_func",uVar1);
  uVar4 = *puVar2;
  uVar1 = FUN_00029510(*(undefined4 *)(unaff_r5 + 0x10c));
  FUN_00026a54(uVar4,"postlex_func",uVar1);
  uVar4 = *puVar2;
  uVar1 = FUN_0004437c(iVar3);
  FUN_00026a54(uVar4,"phoneset",uVar1);
  FUN_00026b3c(*puVar2,"silence",*(undefined4 *)(iVar3 + 0x10));
  FUN_00026b3c(*puVar2,"text_whitespace",*(undefined4 *)(unaff_r5 + 0x23c));
  FUN_00026b3c(*puVar2,"text_postpunctuation",*(undefined4 *)(unaff_r5 + 0x1bc));
  FUN_00026b3c(*puVar2,"text_prepunctuation",*(undefined4 *)(unaff_r5 + 0x3a8));
  FUN_00026b3c(*puVar2,"text_singlecharsymbols",*(undefined4 *)(unaff_r5 + 0x2dc));
  uVar4 = *puVar2;
  uVar1 = FUN_00028fa0(*(undefined4 *)(unaff_r5 + 0x25c));
  FUN_00026a54(uVar4,"sentence_boundary_func",uVar1);
  uVar4 = *puVar2;
  uVar1 = FUN_00028fa0(*(undefined4 *)(unaff_r5 + 0x160));
  FUN_00026a54(uVar4,"tokentowords_func",uVar1);
  uVar4 = *puVar2;
  uVar1 = FUN_00028fa0(*(undefined4 *)(unaff_r5 + 0x438));
  FUN_00026a54(uVar4,"phrasesylendtone_func",uVar1);
  uVar1 = puVar2[1];
  FUN_00044460();
  FUN_0003d9b0(uVar1,&DAT_000717fc,&LAB_00032a3c);
  FUN_0003d9b0(uVar1,"num_digits",&LAB_00032a1c);
  return;
}



// ----- 00032b70 : queried -----
// function: FUN_00032b70 @ 00032b70

undefined4 FUN_00032b70(undefined4 param_1)

{
  int iVar1;
  char *pcVar2;
  int iVar3;
  undefined4 uVar4;
  int iVar5;
  
  for (iVar1 = FUN_00029108(param_1,"Phrase"); iVar1 != 0; iVar1 = FUN_00028c14(iVar1)) {
    pcVar2 = (char *)FUN_00028dc0(iVar1,"name");
    iVar3 = strcmp(pcVar2,"BB");
    if (iVar3 == 0) break;
  }
  iVar3 = FUN_00029108(param_1,"Phrase");
  while( true ) {
    if (iVar3 == 0) {
      return 0;
    }
    iVar5 = FUN_00028c20(iVar3);
    if (iVar5 == 0) break;
    uVar4 = FUN_00028c20(iVar3);
    pcVar2 = (char *)FUN_00028dc0(uVar4,"name");
    iVar5 = strcmp(pcVar2,"BB");
    if (iVar5 == 0) break;
    iVar3 = FUN_00028c20(iVar3);
  }
  if (iVar3 == 0) {
    return 0;
  }
  do {
    pcVar2 = (char *)FUN_0003de24(iVar3,"daughter.gpos");
    iVar5 = strcmp("wp",pcVar2);
    if (iVar5 == 0) {
      return 1;
    }
    pcVar2 = (char *)FUN_0003de24(iVar3,"daughter.gpos");
    iVar5 = strcmp("cc",pcVar2);
    if (iVar5 == 0) {
      pcVar2 = (char *)FUN_0003de24(iVar3,"daughter.n.gpos");
      iVar5 = strcmp("wp",pcVar2);
      if (iVar5 == 0) {
        return 1;
      }
    }
    iVar5 = FUN_00028d04(iVar3,iVar1);
  } while ((iVar5 == 0) && (iVar3 = FUN_00028c14(iVar3), iVar3 != 0));
  return 0;
}



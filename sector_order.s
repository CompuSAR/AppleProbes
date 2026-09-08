IWM_MOTOR_ON    .eq     $c089           ;starts drive spinning
IWM_SEL_DRIVE_1 .eq     $c08a           ;selects drive 1
IWM_Q6_OFF      .eq     $c08c           ;read
IWM_Q7_OFF      .eq     $c08e           ;WP sense/read

LOC0            .eq     $00
LOC1            .eq     $01
PRBYTE          .eq     $FDDA           ; ROM print byte in A in HEX
COUT            .eq     $FDED           ; Print char in A

    .org $1000
    lda #hello>>8
    sta LOC1
    lda #hello&$ff
    sta LOC0

Print:
    ldy #0
    jmp .enter
.out
    jsr COUT
    iny
.enter
    lda (LOC0),y
    bne .out
    rts
hello:  .db "Hello, world", 13, 0

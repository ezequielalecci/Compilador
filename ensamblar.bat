@echo off
\masm32\bin\ml /c /coff salida.asm
if errorlevel 1 goto fin
\masm32\bin\link /SUBSYSTEM:WINDOWS /LIBPATH:\masm32\lib salida.obj
if errorlevel 1 goto fin
salida.exe
:fin
pause

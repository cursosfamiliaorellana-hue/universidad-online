Set objFSO = CreateObject("Scripting.FileSystemObject")
strScriptPath = WScript.ScriptFullName
strCurrentDir = objFSO.GetParentFolderName(strScriptPath)

Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = strCurrentDir

' Ejecutar el orquestador en segundo plano sin ventana negra (0 = Oculto, False = No esperar)
WshShell.Run "cmd /c """ & strCurrentDir & "\2_Iniciar_Bot_Automatico.bat""", 0, False

Set WshShell = Nothing
Set objFSO = Nothing

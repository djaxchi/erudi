!macro customUnInstall
  ; Remove resources directory if it still exists
  RMDir /r "$INSTDIR\resources"

  ; Attempt to remove the installation directory itself if now empty.
  ; (Non-recursive so it only succeeds when truly empty, avoiding accidental wider deletion.)
  RMDir "$INSTDIR"
!macroend

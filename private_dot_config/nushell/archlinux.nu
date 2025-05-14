# If “kime” is installed
if (which kime | is-not-empty) {
    export-env {
        $env.GTK_IM_MODULE = 'kime'
        $env.QT_IM_MODULE  = 'kime'
        $env.XMODIFIERS    = '@im=kime'
    }
} else if (which fcitx5 | is-not-empty) {
    export-env {
        $env.GTK_IM_MODULE = 'fcitx'
        $env.QT_IM_MODULE  = 'fcitx'
        $env.XMODIFIERS    = '@im=fcitx'
    }
}

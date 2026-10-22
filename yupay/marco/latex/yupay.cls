%% =====================================================================
%%  yupay.cls  --  BASE LaTeX de Yupay (rendición de cuentas y finanzas)
%% ---------------------------------------------------------------------
%%  Fase 10.2b de la plataforma Qillqa (2026-10-20). Yupay lleva su propio
%%  marco para que sus anexos no dependan de Gestión documental
%%  (docs/plataforma/propuesta-repositorios.md §3.5): una base pequeña,
%%  pensada para formularios y reportes financieros. El aspecto coincide con
%%  el de los documentos de la entidad SIN compartir código, porque las dos
%%  bases leen la misma marca:
%%    - colores: los de Unancha (tokens/colors.json), que el compilador
%%      escribe en yupay-marca.tex; sin ese archivo, los mismos valores aquí;
%%    - tipografía: Source Serif 4 (cuerpo), Archivo (títulos), Inter (datos),
%%      vendorizadas en ../fuentes (SIL OFL), cargadas por nombre de archivo;
%%    - el titular: el perfil de la institución (perfil-despacho.tex, por
%%      TEXINPUTS); si falta, los datos quedan como renglón para llenar.
%%  Motor: LuaLaTeX (fontspec + polyglossia). Compila el módulo
%%  (rendicion_marco/__init__.py), que arma TEXINPUTS y TTFONTS.
%%  Cada cambio de la marca se prueba con los PDF de las dos bases.
%% =====================================================================
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{yupay}[2026/10/20 v0.1 Base LaTeX de Yupay]
\DeclareOption*{\PassOptionsToClass{\CurrentOption}{article}}
\ProcessOptions\relax
\LoadClass[a4paper,10pt]{article}

\RequirePackage{graphicx}
\RequirePackage{microtype}
\RequirePackage{longtable}
\RequirePackage{booktabs}

%% --- Metadatos: \setmeta{clave}{valor}, \meta{clave}, \ifmetadef ------
\newcommand{\setmeta}[2]{\expandafter\def\csname yupay@meta@#1\endcsname{#2}}
\newcommand{\meta}[1]{%
  \ifcsname yupay@meta@#1\endcsname\csname yupay@meta@#1\endcsname\else\textbf{¿¿#1??}\fi}
% \ifmetadef{clave}{si-definido-y-no-vacio}{si-no}
\newcommand{\ifmetadef}[3]{%
  \ifcsname yupay@meta@#1\endcsname
    \expandafter\ifx\csname yupay@meta@#1\endcsname\empty #3\else #2\fi
  \else #3\fi}

%% --- Colores (por rol; los valores, de Unancha) ----------------------
\RequirePackage{xcolor}
\definecolor{papel}{HTML}{F5F1EC}        % neutral.100: fondo de las cabeceras de tabla
\definecolor{neutral500}{HTML}{A99E92}   % filetes
\definecolor{neutral700}{HTML}{6E655D}   % textos secundarios
\definecolor{tinta}{HTML}{241F1C}        % neutral.900: texto principal
\definecolor{puka800}{HTML}{6E0F22}      % enlaces
\definecolor{guindaoficial}{HTML}{4D1018}% la guinda del logo de la institución (no es de la marca)
\InputIfFileExists{yupay-marca.tex}{}{}  % los tokens de Unancha, si el compilador los encontró
\colorlet{colorenlaces}{puka800}

%% --- Tipografía ---------------------------------------------------------
\RequirePackage{fontspec}
\setmainfont{SourceSerif4-Regular.ttf}[
  BoldFont = SourceSerif4-Bold.ttf, ItalicFont = SourceSerif4-Italic.ttf,
  BoldItalicFont = SourceSerif4-BoldItalic.ttf, Ligatures = TeX]
\newfontfamily{\seriesemi}{SourceSerif4-SemiBold.ttf}[Ligatures=TeX]
\newfontfamily{\fuentedisplaysemi}{Archivo-SemiBold.ttf}[Ligatures=TeX]
\newfontfamily{\fuentedatos}{Inter-Regular.ttf}[BoldFont = Inter-Bold.ttf, Ligatures = TeX, RawFeature = {+tnum}]
\newfontfamily{\fuentedatossemi}{Inter-SemiBold.ttf}[Ligatures = TeX, RawFeature = {+tnum}]

%% --- Idioma: castellano, sin partir palabras (estilo de formulario) -----
\RequirePackage{polyglossia}
\setdefaultlanguage[variant=spanish]{spanish}
\RequirePackage[autostyle=false,style=american]{csquotes}
\hyphenpenalty=10000\relax
\exhyphenpenalty=10000\relax
\tolerance=1000\relax
\emergencystretch=3em\relax

%% --- Página: A4, márgenes de formulario; cabecera y pie los pone la clase
\RequirePackage[a4paper, includehead, top=1.20cm, headheight=0.95cm, headsep=0.45cm,
  left=2.54cm, right=2.54cm, bottom=2.10cm, footskip=1.00cm]{geometry}
\RequirePackage{fancyhdr}
\RequirePackage{lastpage}
\fancypagestyle{yupay}{%
  \fancyhf{}%
  \renewcommand{\headrulewidth}{0pt}%
  \renewcommand{\footrulewidth}{0pt}}
\pagestyle{yupay}

%% --- Espaciado ----------------------------------------------------------
\RequirePackage{setspace}
\setstretch{1.15}
\newcommand{\setsangriaparrafo}[1]{\setlength{\parindent}{#1}}
\newcommand{\setespacioparrafos}[1]{\setlength{\parskip}{#1}}
\setsangriaparrafo{0pt}
\setespacioparrafos{4pt}
\interfootnotelinepenalty=10000\relax

%% --- El titular: el perfil de la institución (el mismo que lee el marco) -
%%  Lo que el perfil define para otros documentos (retratos, sello, banda) no
%%  se usa aquí: esas órdenes se aceptan y se ignoran.
\providecommand{\setbandafoto}[1]{}
\providecommand{\setbandaconsigna}[1]{}
\providecommand{\setselloimagen}[1]{}
\providecommand{\setretratocuerpo}[1]{}
\providecommand{\setretratobusto}[1]{}
\InputIfFileExists{perfil-despacho.tex}{}{}

%% --- Enlaces y datos del PDF (siempre al final) -------------------------
\RequirePackage{xurl}
\RequirePackage[colorlinks=true, breaklinks=true]{hyperref}
\hypersetup{linkcolor=colorenlaces, urlcolor=colorenlaces, citecolor=colorenlaces, filecolor=colorenlaces}
\AtBeginDocument{\hypersetup{
  pdftitle={\ifmetadef{titulopdf}{\meta{titulopdf}}{Yupay}},
  pdfauthor={\ifmetadef{autorpdf}{\meta{autorpdf}}{}},
  pdflang={es-PE}}}

\endinput

%% =====================================================================
%%  yupay-rendicion.cls  --  RENDICIÓN DE VIÁTICOS (Anexos 3 y 4)
%% ---------------------------------------------------------------------
%%  Sobre la base de Yupay (yupay.cls; 2026-10-20). Antes era
%%  marco_documental/classes/rendicion-viaticos.cls (2026-10-18), sobre el
%%  núcleo de la entidad; el formulario y sus medidas no cambian:
%%     Anexo N.° 3 -- Formato N.° 02-VN  Declaración jurada de gastos sin
%%                                       comprobante
%%     Anexo N.° 4 -- Formato N.° 03-VN  Rendición de cuentas por viáticos,
%%                                       pasajes terrestres y/u otros recursos
%%  Son FORMATOS de la institución: sin membrete, sin marca de agua y sin
%%  sello. La cabecera repite el nombre de la directiva y el pie, su
%%  procedencia y el folio. Lo genera Rendición de cuentas
%%  (servicios/rendicion_tex.py); no se numera.
%%
%%  Uso:  \documentclass{yupay-rendicion}
%% =====================================================================
\NeedsTeXFormat{LaTeX2e}
\ProvidesClass{yupay-rendicion}[2026/10/20 v1.1 Yupay: rendición de viáticos]
\DeclareOption*{\PassOptionsToClass{\CurrentOption}{yupay}}
\ProcessOptions\relax
\LoadClass{yupay}

\setmeta{tipodoc}{Rendición de viáticos}
\setmeta{anio}{\the\year}
\RequirePackage{yupay-rendicion}
\fancyhead[C]{\cabeceraformato}
\fancyfoot[C]{\pieformato}
%% El título del PDF: la rendición y su comisionado.
\setmeta{titulopdf}{Rendición de viáticos}
\setmeta{autorpdf}{\ifmetadef{comisionado}{\meta{comisionado}}{}}

\endinput

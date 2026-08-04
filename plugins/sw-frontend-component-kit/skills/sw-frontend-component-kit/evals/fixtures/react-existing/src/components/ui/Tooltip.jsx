import './Tooltip.css'

/**
 * Tooltip — dica contextual ao passar o mouse / focar.
 *
 * | prop     | tipo                              | padrão   | descrição                        |
 * |----------|-----------------------------------|----------|----------------------------------|
 * | label    | string                            | —        | texto da dica                    |
 * | side     | 'top' | 'bottom' | 'left' | 'right'| 'top'    | lado em que aparece              |
 * | children | ReactNode                         | —        | elemento-alvo                    |
 *
 * Ex.: <Tooltip label="Salvar"><button>💾</button></Tooltip>
 */
export function Tooltip({ label, side = 'top', children }) {
  return (
    <span className="ui-tooltip" data-side={side}>
      {children}
      <span className="ui-tooltip__bubble" role="tooltip">{label}</span>
    </span>
  )
}

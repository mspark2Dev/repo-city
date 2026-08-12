import { LOCALES, type Locale } from './messages'
import { useLocaleStore } from '.'

const ORDER: Locale[] = ['en', 'ko']

export function LocaleToggle() {
  const locale = useLocaleStore((s) => s.locale)
  const setLocale = useLocaleStore((s) => s.setLocale)

  return (
    <div className="locale-toggle" role="group">
      {ORDER.map((code) => (
        <button
          key={code}
          type="button"
          className={code === locale ? 'on' : ''}
          onClick={() => setLocale(code)}
          lang={code}
        >
          {LOCALES[code].localeName}
        </button>
      ))}
    </div>
  )
}

import { useEffect, useRef, useState } from 'react'

export type OptionListe = { id: number | string; libelle: string }

const libelle = (m: OptionListe) => m.libelle
const sansAccent = (t: string) => t.normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase()

/** Choix d'un élément d'une liste (matériel, client, fournisseur, salarié, article…). Liste déroulante quand ils sont
 * peu nombreux ; au-delà, on tape quelques lettres et on choisit dans les propositions. */
export default function ChoixListe({ options, value, onChange, required, disabled, vide = 'Choisir…' }: {
  options: OptionListe[]
  value: string
  onChange: (id: string) => void
  required?: boolean
  disabled?: boolean
  vide?: string
}) {
  const choisi = options.find((m) => String(m.id) === value)
  const [texte, setTexte] = useState('')
  const [ouvert, setOuvert] = useState(false)
  const [rang, setRang] = useState(0)
  const champ = useRef<HTMLInputElement>(null)

  useEffect(() => { setTexte(choisi ? libelle(choisi) : '') }, [choisi?.id])   // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    champ.current?.setCustomValidity(required && !choisi ? 'Choisissez dans la liste.' : texte && !choisi ? 'Choisissez dans la liste ou videz le champ.' : '')
  }, [required, choisi, texte])

  if (options.length <= 15) {
    return (
      <select required={required} disabled={disabled} value={value} onChange={(e) => onChange(e.target.value)}>
        <option value="">{vide}</option>
        {options.map((m) => <option key={m.id} value={m.id}>{libelle(m)}</option>)}
      </select>
    )
  }

  const mots = sansAccent(texte).split(/\s+/).filter(Boolean)
  const trouves = choisi && texte === libelle(choisi) ? [] : options.filter((m) => { const l = sansAccent(libelle(m)); return mots.every((x) => l.includes(x)) })
  const propositions = trouves.slice(0, 30)

  function choisir(m: OptionListe) {
    onChange(String(m.id))
    setTexte(libelle(m))
    setOuvert(false)
  }

  return (
    <span className="choix-recherche">
      <input
        ref={champ} type="search" autoComplete="off" disabled={disabled} value={texte} role="combobox" aria-expanded={ouvert} aria-autocomplete="list"
        placeholder={`${vide === 'Choisir…' ? 'Chercher' : vide} : quelques lettres…`}
        onFocus={() => setOuvert(true)}
        onBlur={() => setTimeout(() => setOuvert(false), 150)}
        onChange={(e) => { setTexte(e.target.value); setOuvert(true); setRang(0); if (choisi) onChange('') }}
        onKeyDown={(e) => {
          if (!ouvert || propositions.length === 0) return
          if (e.key === 'ArrowDown') { e.preventDefault(); setRang((r) => Math.min(r + 1, propositions.length - 1)) }
          if (e.key === 'ArrowUp') { e.preventDefault(); setRang((r) => Math.max(r - 1, 0)) }
          if (e.key === 'Enter') { e.preventDefault(); choisir(propositions[rang]) }
          if (e.key === 'Escape') setOuvert(false)
        }}
      />
      {ouvert && !choisi && (
        <ul role="listbox">
          {propositions.map((m, i) => (
            <li key={m.id} role="option" aria-selected={i === rang} onMouseDown={(e) => { e.preventDefault(); choisir(m) }}>{libelle(m)}</li>
          ))}
          {trouves.length === 0 && <li className="aide">Aucun résultat ne correspond.</li>}
          {trouves.length > propositions.length && <li className="aide">{trouves.length - propositions.length} autres : précisez la recherche.</li>}
        </ul>
      )}
    </span>
  )
}

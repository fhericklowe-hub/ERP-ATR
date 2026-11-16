import { type FormEvent, useEffect, useState } from 'react'
import { api } from './api'

type Groupe = { titre: string; autres: boolean; resultats: { titre: string; detail: string; statut: string; chemin: string }[] }

/** Recherche globale : un numéro, un nom, une immatriculation… cherché dans toutes les rubriques ouvertes à l'utilisateur. */
export default function Recherche({ mot }: { mot: string }) {
  const [saisie, setSaisie] = useState(mot)
  const [groupes, setGroupes] = useState<Groupe[] | null>(null)
  const [erreur, setErreur] = useState('')

  useEffect(() => { setSaisie(mot) }, [mot])
  useEffect(() => {
    if (mot.trim().length < 2) { setGroupes([]); return }
    let actuel = true
    setGroupes(null)
    setErreur('')
    api<{ groupes: Groupe[] }>(`/recherche/?search=${encodeURIComponent(mot)}`)
      .then((r) => { if (actuel) setGroupes(r.groupes) })
      .catch((e: Error) => { if (actuel) setErreur(e.message) })
    return () => { actuel = false }
  }, [mot])

  function envoyer(e: FormEvent) {
    e.preventDefault()
    location.hash = `#/recherche?q=${encodeURIComponent(saisie.trim())}`
  }

  const total = (groupes ?? []).reduce((n, g) => n + g.resultats.length, 0)
  return (
    <>
      <h2>Recherche</h2>
      <form className="filtres" onSubmit={envoyer} role="search">
        <input type="search" autoFocus placeholder="Numéro, nom, immatriculation, référence…" value={saisie} onChange={(e) => setSaisie(e.target.value)} />
        <button>Chercher</button>
      </form>
      {erreur && <p className="erreur" role="alert">{erreur}</p>}
      {mot.trim().length < 2 ? <p className="aide">Tapez au moins deux caractères : un numéro de document, un numéro de parc, un nom de client ou de fournisseur, un numéro d'OR.</p>
        : groupes === null ? !erreur && <p>Recherche…</p>
        : total === 0 ? <p>Rien ne correspond à « {mot} » dans les rubriques qui vous sont ouvertes.</p>
        : groupes.map((g) => (
          <section key={g.titre}>
            <h3>{g.titre}</h3>
            <ul className="resultats">
              {g.resultats.map((r) => (
                <li key={r.chemin + r.titre}>
                  <a href={`#${r.chemin}`}><strong>{r.titre}</strong>{r.detail && <span> {r.detail}</span>}</a>
                  {r.statut && <span className="pastille">{r.statut}</span>}
                </li>
              ))}
            </ul>
            {g.autres && <p className="aide">D'autres résultats existent dans cette rubrique : précisez la recherche.</p>}
          </section>
        ))}
    </>
  )
}

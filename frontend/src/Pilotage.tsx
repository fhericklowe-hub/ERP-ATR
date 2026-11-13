import { useEffect, useState } from 'react'
import { api } from './api'

type Indicateur = { libelle: string; valeur: string; alerte: boolean }
type Module = { module: string; lien: string; indicateurs: Indicateur[] }

/** Tableau de bord de direction : les chiffres clés de chaque module, calculés à l'ouverture de la page. */
export default function Pilotage() {
  const [modules, setModules] = useState<Module[] | null>(null)
  const [erreur, setErreur] = useState('')
  useEffect(() => {
    api<Module[]>('/pilotage/').then(setModules).catch((e: Error) => setErreur(e.message))
  }, [])
  return (
    <>
      <div className="barre">
        <h2>Tableau de bord</h2>
        <span className="aide">Situation au {new Date().toLocaleDateString('fr-FR')} · « ce mois » : le mois civil en cours</span>
      </div>
      {erreur && <p className="erreur">{erreur}</p>}
      {!modules && !erreur && <p>Chargement…</p>}
      <div className="pilotage">
        {modules?.map((m) => (
          <fieldset key={m.module}>
            <legend><a href={`#${m.lien}`}>{m.module}</a></legend>
            <dl>
              {m.indicateurs.map((i) => (
                <div key={i.libelle}>
                  <dt>{i.libelle}</dt>
                  <dd>{i.alerte ? <span className="pastille u1">{i.valeur}</span> : <strong>{i.valeur}</strong>}</dd>
                </div>
              ))}
            </dl>
          </fieldset>
        ))}
      </div>
    </>
  )
}

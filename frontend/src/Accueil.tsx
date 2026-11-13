import { useEffect, useState } from 'react'
import { api, type Utilisateur } from './api'

type Rubrique = { titre: string; lien: string; nombre: number; lignes: string[] }

/** Ce que chacun peut lancer d'ici, selon ses droits. */
const RACCOURCIS = [
  { texte: "Nouvelle demande d'achat", chemin: '/demandes/nouvelle', droit: 'achats.add_demandeachat' },
  { texte: 'Demander une sortie de stock', chemin: '/stock/demandes', droit: 'stock.add_demandesortie' },
  { texte: 'Demander une intervention', chemin: '/interventions/nouvelle', droit: 'moyens.add_demandeintervention' },
  { texte: 'Déclarer un événement HSE', chemin: '/hse/nouveau', droit: 'hse.add_evenement' },
  { texte: 'Demander un congé', chemin: '/absences/nouvelle', droit: 'rh.add_demandeabsence' },
]

/** Page d'accueil : ce qui attend l'utilisateur dans tous les modules, et ses raccourcis. */
export default function Accueil({ moi }: { moi: Utilisateur }) {
  const [rubriques, setRubriques] = useState<Rubrique[] | null>(null)
  const [erreur, setErreur] = useState('')
  useEffect(() => {
    api<Rubrique[]>('/accueil/').then(setRubriques).catch((e: Error) => setErreur(e.message))
  }, [])
  const raccourcis = RACCOURCIS.filter((r) => moi.droits.includes(r.droit))
  const total = (rubriques ?? []).reduce((n, r) => n + r.nombre, 0)
  return (
    <div className="fiche">
      <h2>Bonjour {moi.first_name || moi.username}</h2>
      {raccourcis.length > 0 && <div className="actions">{raccourcis.map((r) => <a key={r.chemin} className="bouton secondaire" href={`#${r.chemin}`}>{r.texte}</a>)}</div>}
      {erreur && <p className="erreur">{erreur}</p>}
      {!rubriques && !erreur && <p>Chargement…</p>}
      {rubriques && <p className="statut">{total === 0 ? "Rien n'attend votre action aujourd'hui." : `${total} point${total > 1 ? 's' : ''} attend${total > 1 ? 'ent' : ''} votre action`}</p>}
      {rubriques?.map((r) => (
        <fieldset key={r.titre}>
          <legend>{r.titre} <span className="pastille partielle">{r.nombre}</span></legend>
          <ul>{r.lignes.map((l) => <li key={l}>{l}</li>)}</ul>
          {r.nombre > r.lignes.length && <p className="aide">… et {r.nombre - r.lignes.length} de plus.</p>}
          {r.lien && <p><a href={`#${r.lien}`}>Ouvrir →</a></p>}
        </fieldset>
      ))}
    </div>
  )
}

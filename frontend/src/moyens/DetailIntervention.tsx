import { useCallback, useEffect, useState } from 'react'
import { api, type Page, type Tiers } from '../api'
import { montant } from '../achats/commandes'
import { dateFr, dateHeureFr } from '../achats/types'
import type { Intervention } from './types'

type Personne = { id: number; first_name: string; last_name: string; username: string }

export default function DetailIntervention({ id }: { id: number }) {
  const [d, setD] = useState<Intervention | null>(null)
  const [personnes, setPersonnes] = useState<Personne[]>([])
  const [prestataires, setPrestataires] = useState<Tiers[]>([])
  const [affectation, setAffectation] = useState({ intervenant: '', prestataire: '', date_prevue: '' })
  const [realisation, setRealisation] = useState({ compte_rendu: '', cout: '' })
  const [texte, setTexte] = useState('')
  const [erreur, setErreur] = useState('')
  const [enCours, setEnCours] = useState(false)

  const charger = useCallback(() => {
    api<Intervention>(`/moyens/interventions/${id}/`).then((x) => {
      setD(x)
      setAffectation({ intervenant: String(x.intervenant ?? ''), prestataire: String(x.prestataire ?? ''), date_prevue: x.date_prevue ?? '' })
      if (x.peut_traiter) {
        api<Page<Personne>>('/utilisateurs/?is_active=true&page_size=200').then((p) => setPersonnes(p.results)).catch(() => undefined)
        api<Page<Tiers>>('/tiers/?est_fournisseur=true&actif=true').then((p) => setPrestataires(p.results)).catch(() => undefined)
      }
    }).catch((e: Error) => setErreur(e.message))
  }, [id])
  useEffect(charger, [charger])

  async function agir(action: string, corps: object = {}) {
    setEnCours(true)
    setErreur('')
    try {
      setD(await api<Intervention>(`/moyens/interventions/${id}/${action}/`, { method: 'POST', body: JSON.stringify(corps) }))
      setTexte('')
    } catch (e) {
      setErreur((e as Error).message)
    } finally {
      setEnCours(false)
    }
  }

  if (!d) return erreur ? <p className="erreur">{erreur}</p> : <p>Chargement…</p>
  const ouverte = d.statut === 'NOUVELLE' || d.statut === 'EN_COURS'

  return (
    <div className="fiche">
      <p><a href="#/interventions">← Demandes d'intervention</a></p>
      <div className="barre"><h2>{d.numero}</h2></div>
      <p className="statut">{d.statut_libelle}{d.priorite === 1 && <> <span className="pastille u1">Urgente</span></>}</p>

      <dl>
        <dt>Objet</dt><dd><strong>{d.objet}</strong></dd>
        <dt>Catégorie</dt><dd>{d.categorie_libelle} · priorité : {d.priorite_libelle}</dd>
        {d.description && <><dt>Description</dt><dd>{d.description}</dd></>}
        <dt>Lieu</dt><dd>{d.site_nom}{d.lieu && ` · ${d.lieu}`}</dd>
        {d.bien_nom && <><dt>Bien concerné</dt><dd>{d.bien_nom}</dd></>}
        <dt>Demandeur</dt><dd>{d.demandeur_nom} · {d.service_nom} · le {dateHeureFr(d.cree_le)}</dd>
        {(d.intervenant_nom || d.prestataire_nom) && (
          <><dt>Intervenant</dt><dd>{[d.intervenant_nom, d.prestataire_nom].filter(Boolean).join(', ')}{d.date_prevue && ` · prévue le ${dateFr(d.date_prevue)}`}</dd></>
        )}
        {d.compte_rendu && <><dt>Compte rendu</dt><dd>{d.compte_rendu}{d.realisee_le && ` (le ${dateFr(d.realisee_le)})`}</dd></>}
        {d.cout && <><dt>Coût</dt><dd>{montant(d.cout)} XOF</dd></>}
      </dl>

      {erreur && <p className="erreur" role="alert">{erreur}</p>}

      {d.modifiable && <div className="actions"><a className="bouton secondaire" href={`#/interventions/${d.id}/modifier`}>Modifier ma demande</a></div>}

      {d.peut_traiter && ouverte && (
        <fieldset>
          <legend>{d.statut === 'NOUVELLE' ? 'Prendre en charge' : "Changer l'affectation"}</legend>
          <div className="grille">
            <label>Intervenant interne
              <select value={affectation.intervenant} onChange={(e) => setAffectation({ ...affectation, intervenant: e.target.value })}>
                <option value="">Aucun</option>
                {personnes.map((p) => <option key={p.id} value={p.id}>{`${p.first_name} ${p.last_name}`.trim() || p.username}</option>)}
              </select>
            </label>
            <label>Prestataire
              <select value={affectation.prestataire} onChange={(e) => setAffectation({ ...affectation, prestataire: e.target.value })}>
                <option value="">Aucun</option>
                {prestataires.map((p) => <option key={p.id} value={p.id}>{p.raison_sociale}</option>)}
              </select>
            </label>
            <label>Date prévue
              <input type="date" value={affectation.date_prevue} onChange={(e) => setAffectation({ ...affectation, date_prevue: e.target.value })} />
            </label>
          </div>
          <div className="actions">
            <button disabled={enCours} onClick={() => agir('prendre_en_charge', affectation)}>
              {d.statut === 'NOUVELLE' ? 'Prendre en charge' : "Enregistrer l'affectation"}
            </button>
          </div>
        </fieldset>
      )}

      {d.peut_realiser && (
        <fieldset>
          <legend>Intervention réalisée</legend>
          <label>Compte rendu : ce qui a été fait
            <textarea value={realisation.compte_rendu} onChange={(e) => setRealisation({ ...realisation, compte_rendu: e.target.value })} />
          </label>
          <label>Coût (XOF, facultatif)
            <input type="number" min="0" step="1" value={realisation.cout} onChange={(e) => setRealisation({ ...realisation, cout: e.target.value })} />
          </label>
          <div className="actions">
            <button disabled={enCours} onClick={() => agir('realiser', realisation)}>Déclarer l'intervention réalisée</button>
          </div>
        </fieldset>
      )}

      {((d.peut_cloturer && (d.statut === 'REALISEE' || d.statut === 'CLOTUREE')) || (d.peut_traiter && ouverte)) && (
        <fieldset>
          <legend>{d.statut === 'REALISEE' ? 'Le problème est-il réglé ?' : d.statut === 'CLOTUREE' ? 'Le problème est revenu ?' : 'Refuser la demande'}</legend>
          <label>Commentaire ou motif
            <textarea value={texte} onChange={(e) => setTexte(e.target.value)} />
          </label>
          <div className="actions">
            {d.statut === 'REALISEE' && <button disabled={enCours} onClick={() => agir('cloturer', { commentaire: texte })}>Oui, clôturer</button>}
            {(d.statut === 'REALISEE' || d.statut === 'CLOTUREE') && (
              <button className="secondaire" disabled={enCours} onClick={() => agir('rouvrir', { commentaire: texte })}>Non, rouvrir la demande</button>
            )}
            {ouverte && <button className="danger" disabled={enCours} onClick={() => agir('refuser', { commentaire: texte })}>Refuser</button>}
          </div>
        </fieldset>
      )}

      <h3>Historique</h3>
      {d.evenements.length === 0 && <p className="aide">En attente de prise en charge par les moyens généraux.</p>}
      <ul>
        {d.evenements.map((e) => (
          <li key={e.id}>{dateHeureFr(e.date)} · <strong>{e.action_libelle}</strong> par {e.auteur_nom}{e.commentaire && ` : ${e.commentaire}`}</li>
        ))}
      </ul>
    </div>
  )
}

import { type ChangeEvent, useCallback, useEffect, useState } from 'react'
import { api, type Page } from '../api'
import type { Commande } from './commandes'
import { type Acheteur, type Demande, URGENCES, dateFr, dateHeureFr } from './types'

export default function Detail({ id, moiId, droits }: { id: number; moiId: number; droits: string[] }) {
  const [d, setD] = useState<Demande | null>(null)
  const [erreur, setErreur] = useState('')
  const [texte, setTexte] = useState('')
  const [enCours, setEnCours] = useState(false)
  const [acheteurs, setAcheteurs] = useState<Acheteur[]>([])
  const [commandes, setCommandes] = useState<Commande[]>([])

  const charger = useCallback(() => {
    api<Demande>(`/achats/demandes/${id}/`).then(setD).catch((e: Error) => setErreur(e.message))
  }, [id])
  useEffect(charger, [charger])

  // Bons de commande de la demande, pour ceux qui ont le droit de les voir.
  const validee = d?.statut === 'VALIDEE'
  useEffect(() => {
    if (validee && droits.includes('achats.view_boncommande'))
      api<Page<Commande>>(`/achats/bons-commande/?demande=${id}`).then((p) => setCommandes(p.results)).catch(() => {})
  }, [validee, droits, id])
  const peutCommander = droits.includes('achats.add_boncommande')

  // Seul le responsable achats réattribue : il a besoin de la charge de l'équipe.
  const responsable = d?.statut === 'ATT_ACHATS' && d.peut_valider
  useEffect(() => {
    if (responsable) api<Page<Acheteur>>('/achats/acheteurs/').then((p) => setAcheteurs(p.results)).catch(() => {})
  }, [responsable, d?.acheteur])

  async function agir(action: string, corps: object = {}) {
    setEnCours(true)
    setErreur('')
    try {
      setD(await api<Demande>(`/achats/demandes/${id}/${action}/`, { method: 'POST', body: JSON.stringify(corps) }))
      setTexte('')
    } catch (e) {
      setErreur((e as Error).message)
    } finally {
      setEnCours(false)
    }
  }

  async function joindre(e: ChangeEvent<HTMLInputElement>) {
    const fichier = e.target.files?.[0]
    if (!fichier) return
    const corps = new FormData()
    corps.append('fichier', fichier)
    try {
      await api(`/achats/demandes/${id}/pieces-jointes/`, { method: 'POST', body: corps })
      charger()
    } catch (err) {
      setErreur((err as Error).message)
    }
    e.target.value = ''
  }

  async function controleStock(valeur: string) {
    try {
      setD(await api<Demande>(`/achats/demandes/${id}/`, { method: 'PATCH', body: JSON.stringify({ controle_stock: valeur }) }))
    } catch (e) {
      setErreur((e as Error).message)
    }
  }

  if (!d) return erreur ? <p className="erreur">{erreur}</p> : <p>Chargement…</p>
  const mienne = d.modifiable && d.demandeur === moiId
  const auxAchats = d.statut === 'ATT_ACHATS' && d.peut_valider
  const reattribuable = auxAchats && acheteurs.length > 0

  return (
    <div className="fiche">
      <p><a href="#/">← Demandes d'achat</a></p>
      <div className="barre">
        <h2>{d.numero}</h2>
        <span className={`pastille u${d.urgence}`}>{URGENCES[d.urgence]}</span>
      </div>
      <p className="statut">{d.statut_libelle}</p>
      {d.statut === 'RENVOYEE' && <p className="erreur">Éléments manquants : {d.elements_manquants}</p>}
      {d.echeance_commande && d.statut === 'ATT_ACHATS' && (
        <p className={d.en_retard ? 'erreur' : ''}>
          Fiche complète reçue le {dateHeureFr(d.recue_le)}. Bon de commande attendu avant le {dateHeureFr(d.echeance_commande)}
          {d.en_retard && ' : en retard'}.
        </p>
      )}

      <dl>
        <dt>Demandeur</dt><dd>{d.demandeur_nom} · {d.service_nom} · {d.site_nom} {d.telephone && `· ${d.telephone}`}</dd>
        <dt>Date</dt><dd>{dateFr(d.date_demande)}{d.date_besoin && ` · besoin pour le ${dateFr(d.date_besoin)}`}</dd>
        {d.numero_or && <><dt>Numéro OR</dt><dd>{d.numero_or}</dd></>}
        {d.equipement_designation && (
          <><dt>Équipement</dt>
            <dd>{[d.equipement_designation, d.equipement_marque, d.equipement_modele, d.equipement_serie].filter(Boolean).join(' · ')}</dd></>
        )}
        {d.justification_urgence && <><dt>Justification</dt><dd>{d.justification_urgence}</dd></>}
      </dl>

      <h3>Articles</h3>
      <div className="defilant">
        <table>
          <thead><tr><th>Désignation</th><th>Référence</th><th>Qté</th><th>Observations</th></tr></thead>
          <tbody>
            {d.lignes.map((l) => (
              <tr key={l.id}>
                <td>{l.designation}</td><td>{l.reference_constructeur}</td>
                <td>{Number(l.quantite)} {l.unite_code}</td><td>{l.observations}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <h3>Photos et pièces jointes</h3>
      {d.pieces_jointes.length === 0 && <p className="aide">Aucune pièce jointe.</p>}
      <ul>
        {d.pieces_jointes.map((p) => (
          <li key={p.id}><a href={p.fichier} target="_blank" rel="noreferrer">{decodeURIComponent(p.fichier.split('/').pop() ?? '')}</a></li>
        ))}
      </ul>
      {mienne && (
        <label className="secondaire bouton">
          Ajouter une photo ou un fichier
          <input type="file" accept="image/*,application/pdf" hidden onChange={joindre} />
        </label>
      )}

      {(d.acheteur_nom || d.statut === 'ATT_ACHATS') && (
        <>
          <h3>Acheteur</h3>
          <p className={d.acheteur_nom ? '' : 'erreur'}>{d.acheteur_nom || 'Aucun acheteur disponible : demande à attribuer.'}</p>
          {reattribuable && (
            <label className="filtre">Attribuer à
              <select value="" onChange={(e) => e.target.value && agir('attribuer', { acheteur: Number(e.target.value) })}>
                <option value="">Choisir un acheteur…</option>
                {acheteurs.filter((a) => a.utilisateur !== d.acheteur).map((a) => (
                  <option key={a.id} value={a.id}>
                    {a.nom} · {a.en_cours} en cours{a.disponible ? '' : ' · absent'}
                  </option>
                ))}
              </select>
            </label>
          )}
        </>
      )}

      {d.peut_traiter && (
        <>
          <h3>Contrôle stock</h3>
          <select className="filtre" value={d.controle_stock} onChange={(e) => controleStock(e.target.value)}>
            <option value="">Non contrôlé</option>
            <option value="DISPO">Disponible</option>
            <option value="NON_DISPO">Non disponible</option>
          </select>
        </>
      )}

      {erreur && <p className="erreur" role="alert">{erreur}</p>}

      {mienne && (
        <div className="actions">
          <button disabled={enCours} onClick={() => agir('soumettre')}>Soumettre pour validation</button>
          <a className="bouton secondaire" href={`#/demandes/${d.id}/modifier`}>Modifier</a>
        </div>
      )}

      {(d.peut_valider || d.peut_traiter) && (
        <fieldset>
          <legend>{d.peut_valider ? 'Votre décision' : 'Traitement de la demande'}</legend>
          <label>{d.peut_valider ? 'Commentaire, motif du refus ou éléments manquants' : 'Éléments manquants'}
            <textarea value={texte} onChange={(e) => setTexte(e.target.value)} />
          </label>
          <div className="actions">
            {d.peut_valider && <button disabled={enCours} onClick={() => agir('valider', { commentaire: texte })}>Valider</button>}
            {d.peut_traiter && (
              <button className="secondaire" disabled={enCours} onClick={() => agir('renvoyer', { elements_manquants: texte })}>
                Renvoyer au demandeur (incomplète)
              </button>
            )}
            {d.peut_valider && (
              <button className="danger" disabled={enCours} onClick={() => agir('refuser', { commentaire: texte })}>Refuser</button>
            )}
          </div>
        </fieldset>
      )}

      {d.statut === 'VALIDEE' && (
        <>
          <h3>Bons de commande</h3>
          {commandes.length === 0 && <p className="aide">Aucun bon de commande pour cette demande.</p>}
          <ul>
            {commandes.map((c) => (
              <li key={c.id}><a href={`#/commandes/${c.id}`}>{c.numero}</a> · {c.fournisseur_nom} · {c.statut_libelle}</li>
            ))}
          </ul>
          {peutCommander && <a className="bouton" href={`#/demandes/${d.id}/commander`}>Créer un bon de commande</a>}
        </>
      )}

      <h3>Historique</h3>
      {d.evenements.length === 0 && <p className="aide">Brouillon, pas encore soumis.</p>}
      <ul>
        {d.evenements.map((e) => (
          <li key={e.id}>
            {dateHeureFr(e.date)} · <strong>{e.action_libelle}</strong> par {e.auteur_nom}
            {e.commentaire && ` : ${e.commentaire}`}
          </li>
        ))}
      </ul>
    </div>
  )
}


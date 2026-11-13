import { type FormEvent, useState } from 'react'
import { changerMotDePasse } from './api'

type Moi = { username: string; first_name: string; last_name: string; email?: string; telephone?: string; fonction: string; roles: string[] }

/** Le compte de la personne connectée : ce que l'ERP sait d'elle, ses rôles, et son mot de passe qu'elle change elle-même. */
export default function MonCompte({ moi }: { moi: Moi }) {
  const [saisie, setSaisie] = useState({ actuel: '', nouveau: '', encore: '' })
  const [erreur, setErreur] = useState('')
  const [fait, setFait] = useState(false)
  const [enCours, setEnCours] = useState(false)

  async function changer(e: FormEvent) {
    e.preventDefault()
    setFait(false)
    if (saisie.nouveau !== saisie.encore) return setErreur('Les deux saisies du nouveau mot de passe ne sont pas identiques.')
    setErreur('')
    setEnCours(true)
    try {
      await changerMotDePasse(saisie.actuel, saisie.nouveau)
      setSaisie({ actuel: '', nouveau: '', encore: '' })
      setFait(true)
    } catch (err) {
      setErreur((err as Error).message)
    } finally {
      setEnCours(false)
    }
  }
  const champ = (nom: keyof typeof saisie) => ({ type: 'password', required: true, value: saisie[nom], onChange: (e: { target: { value: string } }) => setSaisie({ ...saisie, [nom]: e.target.value }) })

  return (
    <div className="fiche">
      <h2>Mon compte</h2>
      <fieldset>
        <dl>
          <dt>Identifiant</dt><dd>{moi.username}</dd>
          <dt>Nom</dt><dd>{`${moi.first_name} ${moi.last_name}`.trim() || '—'}</dd>
          <dt>Fonction</dt><dd>{moi.fonction || '—'}</dd>
          <dt>E-mail</dt><dd>{moi.email || '—'}</dd>
          <dt>Téléphone</dt><dd>{moi.telephone || '—'}</dd>
          <dt>Rôles</dt><dd>{moi.roles.length ? moi.roles.join(', ') : 'Aucun'}</dd>
        </dl>
        <p className="aide">Pour corriger ces informations ou vos rôles, adressez-vous à la personne qui gère les comptes.</p>
      </fieldset>
      <form onSubmit={changer}>
        <fieldset>
          <legend>Changer mon mot de passe</legend>
          <div className="grille">
            <label>Mot de passe actuel<input autoComplete="current-password" {...champ('actuel')} /></label>
            <label>Nouveau mot de passe<input autoComplete="new-password" minLength={8} {...champ('nouveau')} /></label>
            <label>Nouveau mot de passe, encore<input autoComplete="new-password" minLength={8} {...champ('encore')} /></label>
          </div>
          <p className="aide">8 caractères au moins, pas uniquement des chiffres, pas un mot de passe courant. Vos autres appareils seront déconnectés.</p>
          {erreur && <p className="erreur" role="alert">{erreur}</p>}
          {fait && <p role="status">Votre mot de passe est changé.</p>}
          <div className="actions"><button disabled={enCours}>{enCours ? 'Enregistrement…' : 'Changer le mot de passe'}</button></div>
        </fieldset>
      </form>
    </div>
  )
}

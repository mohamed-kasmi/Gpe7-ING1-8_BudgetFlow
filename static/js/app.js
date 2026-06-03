// ─── MODAL ───
function openModal(id) {
  document.getElementById(id).classList.add('open');
  document.body.style.overflow = 'hidden';
}

function closeModal(id) {
  document.getElementById(id).classList.remove('open');
  document.body.style.overflow = '';
}

function closeModalOut(e, id) {
  if (e.target === document.getElementById(id)) closeModal(id);
}

// ─── TYPE TOGGLE ───
function setType(btn, type, inputId) {
  const parent = btn.closest('.type-toggle');
  parent.querySelectorAll('.type-btn').forEach(b => b.classList.remove('active'));
  btn.classList.add('active');
  if (inputId) document.getElementById(inputId).value = type;
}

// ─── KEYBOARD ───
document.addEventListener('keydown', e => {
  if (e.key === 'Escape') {
    document.querySelectorAll('.modal-overlay.open').forEach(m => {
      m.classList.remove('open');
      document.body.style.overflow = '';
    });
  }
});

// ─── AUTO-DISMISS MESSAGES ───
document.addEventListener('DOMContentLoaded', () => {
  const banners = document.querySelectorAll('.toast-banner');
  banners.forEach(b => {
    setTimeout(() => {
      b.style.transition = 'opacity .4s';
      b.style.opacity = '0';
      setTimeout(() => b.remove(), 400);
    }, 4000);
  });
});

// ─── CONFIRM DELETES ───
document.querySelectorAll('[data-confirm]').forEach(btn => {
  btn.addEventListener('click', e => {
    if (!confirm(btn.dataset.confirm)) e.preventDefault();
  });
});
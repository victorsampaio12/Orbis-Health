function mascaraDataHora(valor) {
  valor = valor.replace(/\D/g, '');
  if (valor.length > 2) {
    valor = valor.replace(/^(\d{2})(\d)/, '$1/$2');
  }
  if (valor.length > 5) {
    valor = valor.replace(/^(\d{2})\/(\d{2})(\d)/, '$1/$2/$3');
  }
  if (valor.length > 9) {
    valor = valor.replace(/^(\d{2})\/(\d{2})\/(\d{4})(\d)/, '$1/$2/$3 $4');
  }
  if (valor.length > 11) {
    valor = valor.replace(/^(\d{2})\/(\d{2})\/(\d{4}) (\d{2})(\d)/, '$1/$2/$3 $4:$5');
  }
  return valor;
}

function mascaraCPF(valor) {
  return valor
    .replace(/\D/g, '')
    .replace(/(\d{3})(\d)/, '$1.$2')
    .replace(/(\d{3})(\d)/, '$1.$2')
    .replace(/(\d{3})(\d{1,2})$/, '$1-$2');
}

function mascaraTelefone(valor) {
  valor = valor.replace(/\D/g, '');
  if (valor.length > 10) {
    return valor.replace(/^(\d{2})(\d{5})(\d{4}).*/, '($1) $2-$3');
  } else {
    return valor.replace(/^(\d{2})(\d{4})(\d{0,4}).*/, '($1) $2-$3');
  }
}

document.addEventListener('DOMContentLoaded', function () {
  const inputDataHora = document.querySelector('input[name="data_hora"]');
  const cpfInput = document.querySelector('input[name="cpf"]');
  const telefoneInput = document.querySelector('input[name="telefone"]');

  if (inputDataHora) {
    inputDataHora.setAttribute('maxlength', 16);
    inputDataHora.addEventListener('input', e => {
      e.target.value = mascaraDataHora(e.target.value);
    });
  }

  if (cpfInput) {
    cpfInput.setAttribute('maxlength', 14);
    cpfInput.addEventListener('input', e => {
      e.target.value = mascaraCPF(e.target.value);
    });
  }

  if (telefoneInput) {
    telefoneInput.setAttribute('maxlength', 15);
    telefoneInput.addEventListener('input', e => {
      e.target.value = mascaraTelefone(e.target.value);
    });
  }
});

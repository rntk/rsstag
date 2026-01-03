'use strict';
import React from 'react';

export default class LettersList extends React.Component {
  constructor(props) {
    super(props);
    this.state = {
      letters: window.initial_letters_list,
    };
  }

  render() {
    if (this.state && this.state.letters) {
      let letters = [];

      letters = this.state.letters.map((letter) => {
        let splitter = false;

        switch (letter.letter) {
          case 'ё':
          case 'z':
          case '9': {
            splitter = true;
            break;
          }
          default: {
            splitter = false;
          }
        }

        return (
          <span key={letter.letter}>
            <a href={letter.local_url} className="letter">
              {letter.letter}
            </a>
            {splitter ? <br /> : ' '}
          </span>
        );
      });

      return <div className="letters">{letters}</div>;
    } else {
      return <p></p>;
    }
  }
}

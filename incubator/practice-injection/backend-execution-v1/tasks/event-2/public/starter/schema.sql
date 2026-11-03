CREATE TABLE claims(event_id text PRIMARY KEY); CREATE TABLE effects(id serial PRIMARY KEY,event_id text NOT NULL,amount integer NOT NULL CHECK(amount>0));
